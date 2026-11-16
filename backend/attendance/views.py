import csv
import re
import time

from django.conf import settings
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsAdminOrLecturer, IsAdminRole, IsStudentRole

from .models import AttendanceAttempt, AttendanceRecord, Course, Enrollment, LectureSession
from .serializers import CourseSerializer, EnrollSerializer, LectureSessionSerializer, ScanSerializer
from .services import analytics, qr, scan, tokens


# --------------------------------------------------------------------------
# Courses
# --------------------------------------------------------------------------
class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminOrLecturer()]

    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.select_related("lecturer")
        if user.role == User.Role.LECTURER:
            queryset = queryset.filter(lecturer=user)
        elif user.role == User.Role.STUDENT:
            queryset = queryset.filter(
                pk__in=Enrollment.objects.filter(student=user).values("course_id")
            )
        return queryset.annotate(
            student_count=Count("enrollments", distinct=True),
            session_count=Count("sessions", distinct=True),
        )

    @action(detail=True, methods=["get", "post"], url_path="students")
    def students(self, request, pk=None):
        """GET: list the enrolled students. POST: enrol students by their codes."""
        course = self.get_object()
        if request.method == "POST":
            serializer = EnrollSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            codes = sorted(
                {code.strip().upper() for code in serializer.validated_data["neptun_codes"] if code.strip()}
            )
            found = list(User.objects.filter(role=User.Role.STUDENT, neptun_code__in=codes))
            found_codes = {user.neptun_code for user in found}
            existing = set(
                Enrollment.objects.filter(course=course, student__in=found).values_list(
                    "student__neptun_code", flat=True
                )
            )
            new = [Enrollment(course=course, student=user) for user in found if user.neptun_code not in existing]
            Enrollment.objects.bulk_create(new)
            return Response(
                {
                    "added": len(new),
                    "already_enrolled": sorted(existing),
                    "unknown": sorted(set(codes) - found_codes),
                },
                status=status.HTTP_201_CREATED if new else status.HTTP_200_OK,
            )
        rows = course.enrollments.select_related("student").order_by(
            "student__last_name", "student__first_name"
        )
        return Response(
            [
                {
                    "id": row.student_id,
                    "neptun_code": row.student.neptun_code,
                    "name": row.student.display_name,
                    "username": row.student.username,
                }
                for row in rows
            ]
        )

    @action(detail=True, methods=["delete"], url_path=r"students/(?P<student_id>\d+)")
    def remove_student(self, request, pk=None, student_id=None):
        course = self.get_object()
        deleted, _ = Enrollment.objects.filter(course=course, student_id=student_id).delete()
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="analytics")
    def course_analytics(self, request, pk=None):
        return Response(analytics.course_analytics(self.get_object()))


# --------------------------------------------------------------------------
# Lecture sessions
# --------------------------------------------------------------------------
def _csv_safe(value):
    """Neutralise spreadsheet formula injection in exported cells."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


class LectureSessionViewSet(viewsets.ModelViewSet):
    """Session management for lecturers and administrators."""

    serializer_class = LectureSessionSerializer
    permission_classes = [IsAdminOrLecturer]

    def get_queryset(self):
        user = self.request.user
        queryset = LectureSession.objects.select_related("course")
        if user.role == User.Role.LECTURER:
            queryset = queryset.filter(course__lecturer=user)
        course_id = self.request.query_params.get("course")
        if course_id and course_id.isdigit():
            queryset = queryset.filter(course_id=int(course_id))
        return queryset.annotate(
            present_count=Count("records", distinct=True),
            enrolled_count=Count("course__enrollments", distinct=True),
        ).order_by("-starts_at")

    @action(detail=True, methods=["post"])
    def open(self, request, pk=None):
        session = self.get_object()
        if timezone.now() > session.ends_at:
            return Response(
                {"detail": "The end time of this session has passed. Extend it before opening."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        session.open()
        session.save(update_fields=["is_open", "opened_at", "closed_at"])
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        session = self.get_object()
        session.close()
        session.save(update_fields=["is_open", "closed_at"])
        return Response(self.get_serializer(session).data)

    @action(detail=True, methods=["get"])
    def qr(self, request, pk=None):
        """The QR code that is valid right now (rotates every ``interval`` seconds)."""
        session = self.get_object()
        if not session.is_accepting():
            return Response(
                {"detail": "This session is not open for attendance."}, status=status.HTTP_409_CONFLICT
            )
        now = time.time()
        interval = session.qr_interval_seconds
        token = tokens.make_token(session.secret, session.id, interval, now)
        url = f"{settings.FRONTEND_URL.rstrip('/')}/scan?token={token}"
        response = Response(
            {
                "token": token,
                "url": url,
                "image": qr.qr_png_data_uri(url),
                "interval": interval,
                "expires_in": round(tokens.seconds_until_rotation(interval, now), 2),
            }
        )
        response["Cache-Control"] = "no-store"
        return response

    @action(detail=True, methods=["get"])
    def attendance(self, request, pk=None):
        """Roster with present/absent state and the latest rejected attempts."""
        session = self.get_object()
        records = {record.student_id: record for record in session.records.all()}
        enrolments = session.course.enrollments.select_related("student").order_by(
            "student__last_name", "student__first_name"
        )
        rows = []
        for enrolment in enrolments:
            student = enrolment.student
            record = records.get(student.id)
            rows.append(
                {
                    "student_id": student.id,
                    "neptun_code": student.neptun_code,
                    "name": student.display_name,
                    "present": record is not None,
                    "scanned_at": record.scanned_at if record else None,
                    "distance_m": round(record.distance_m, 1) if record else None,
                    "accuracy_m": round(record.accuracy_m, 1) if record else None,
                }
            )
        rejected = (
            AttendanceAttempt.objects.filter(session=session, accepted=False)
            .exclude(reason="ALREADY_RECORDED")
            .select_related("student")[:15]
        )
        return Response(
            {
                "present": sum(1 for row in rows if row["present"]),
                "enrolled": len(rows),
                "is_accepting": session.is_accepting(),
                "rows": rows,
                "recent_rejections": [
                    {
                        "student": attempt.student.display_name,
                        "reason": attempt.reason,
                        "created_at": attempt.created_at,
                        "distance_m": round(attempt.distance_m) if attempt.distance_m is not None else None,
                    }
                    for attempt in rejected
                ],
            }
        )

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        session = self.get_object()
        data = self.attendance(request, pk=pk).data
        safe_code = re.sub(r"[^A-Za-z0-9_-]", "_", session.course.code)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="attendance_{safe_code}_{session.id}.csv"'
        response.write("﻿")  # BOM so that Excel detects UTF-8
        writer = csv.writer(response)
        writer.writerow(["Student code", "Name", "Status", "Checked in at", "Distance (m)", "GPS accuracy (m)"])
        for row in data["rows"]:
            writer.writerow(
                [
                    _csv_safe(row["neptun_code"] or ""),
                    _csv_safe(row["name"]),
                    "present" if row["present"] else "absent",
                    row["scanned_at"].isoformat() if row["scanned_at"] else "",
                    row["distance_m"] if row["distance_m"] is not None else "",
                    row["accuracy_m"] if row["accuracy_m"] is not None else "",
                ]
            )
        return response


# --------------------------------------------------------------------------
# Student check-in and student dashboard
# --------------------------------------------------------------------------
class ScanView(APIView):
    """A student submits the scanned QR token together with the phone's position."""

    permission_classes = [IsStudentRole]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "scan"

    def post(self, request):
        serializer = ScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            record = scan.process_scan(
                student=request.user,
                token=data["token"],
                latitude=data["latitude"],
                longitude=data["longitude"],
                accuracy=data["accuracy"],
            )
        except scan.ScanRejected as rejection:
            return Response(
                {"code": rejection.reason, "detail": rejection.message}, status=rejection.status
            )
        return Response(
            {
                "detail": "Attendance recorded.",
                "course_code": record.session.course.code,
                "course_name": record.session.course.name,
                "session": record.session.title,
                "scanned_at": record.scanned_at,
            },
            status=status.HTTP_201_CREATED,
        )


class MyAttendanceView(APIView):
    """Dashboard data for the logged-in student."""

    permission_classes = [IsStudentRole]

    def get(self, request):
        user = request.user
        courses = list(
            Course.objects.filter(pk__in=Enrollment.objects.filter(student=user).values("course_id"))
            .select_related("lecturer")
            .order_by("code")
        )
        course_ids = [course.id for course in courses]
        held = dict(
            LectureSession.objects.filter(course_id__in=course_ids, opened_at__isnull=False)
            .values_list("course_id")
            .annotate(n=Count("id"))
        )
        attended = dict(
            AttendanceRecord.objects.filter(student=user, session__course_id__in=course_ids)
            .values_list("session__course_id")
            .annotate(n=Count("id"))
        )
        course_rows = []
        for course in courses:
            held_count = held.get(course.id, 0)
            attended_count = attended.get(course.id, 0)
            course_rows.append(
                {
                    "id": course.id,
                    "code": course.code,
                    "name": course.name,
                    "lecturer_name": course.lecturer.display_name,
                    "sessions_held": held_count,
                    "attended": attended_count,
                    "rate": round(100.0 * attended_count / held_count, 1) if held_count else None,
                }
            )

        checked_in = set(
            AttendanceRecord.objects.filter(student=user).values_list("session_id", flat=True)
        )
        open_sessions = LectureSession.objects.filter(
            course_id__in=course_ids, is_open=True, ends_at__gte=timezone.now()
        ).select_related("course")
        recent = AttendanceRecord.objects.filter(student=user).select_related("session__course").order_by(
            "-scanned_at"
        )[:10]

        return Response(
            {
                "courses": course_rows,
                "open_sessions": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "course_code": s.course.code,
                        "course_name": s.course.name,
                        "ends_at": s.ends_at,
                        "checked_in": s.id in checked_in,
                    }
                    for s in open_sessions
                ],
                "recent": [
                    {
                        "session": r.session.title,
                        "course_code": r.session.course.code,
                        "scanned_at": r.scanned_at,
                    }
                    for r in recent
                ],
            }
        )


class OverviewView(APIView):
    """System-wide statistics for administrators."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(analytics.overview())
