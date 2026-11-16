"""Aggregations for the lecturer and administrator dashboards.

Definitions
-----------
* A session is *held* when the lecturer opened it at least once.
* Attendance rate = check-ins / (held sessions x enrolled students).
  Students enrolled later than a session are counted in the denominator; this
  simplification is discussed in the thesis.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import User

from ..models import AttendanceAttempt, AttendanceRecord, Course, LectureSession


def _pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0.0


def course_analytics(course):
    threshold = settings.ATTENDANCE["AT_RISK_THRESHOLD"]
    enrolled = list(
        course.enrollments.select_related("student").order_by("student__last_name", "student__first_name")
    )
    held = list(course.sessions.filter(opened_at__isnull=False).order_by("starts_at"))
    held_ids = [session.id for session in held]

    per_session = dict(
        AttendanceRecord.objects.filter(session_id__in=held_ids)
        .values_list("session_id")
        .annotate(n=Count("id"))
    )
    per_student = dict(
        AttendanceRecord.objects.filter(session_id__in=held_ids)
        .values_list("student_id")
        .annotate(n=Count("id"))
    )

    sessions = [
        {
            "id": s.id,
            "title": s.title,
            "starts_at": s.starts_at,
            "present": per_session.get(s.id, 0),
            "enrolled": len(enrolled),
            "rate": _pct(per_session.get(s.id, 0), len(enrolled)),
        }
        for s in held
    ]

    students = []
    for enrollment in enrolled:
        student = enrollment.student
        present = per_student.get(student.id, 0)
        rate = _pct(present, len(held))
        students.append(
            {
                "id": student.id,
                "name": student.display_name,
                "neptun_code": student.neptun_code,
                "present": present,
                "held": len(held),
                "rate": rate,
                "at_risk": len(held) >= 3 and rate < threshold,
            }
        )

    rejected = dict(
        AttendanceAttempt.objects.filter(session__course=course, accepted=False)
        .values_list("reason")
        .annotate(n=Count("id"))
    )

    total_present = sum(per_session.values())
    return {
        "course": {"id": course.id, "code": course.code, "name": course.name},
        "enrolled": len(enrolled),
        "sessions_held": len(held),
        "average_rate": _pct(total_present, len(held) * len(enrolled)),
        "at_risk_threshold": threshold,
        "sessions": sessions,
        "students": students,
        "rejected_attempts": rejected,
    }


def overview():
    now = timezone.now()
    since_days = 14
    since = now - timedelta(days=since_days)

    users_by_role = dict(User.objects.values_list("role").annotate(n=Count("id")))
    sessions_held = LectureSession.objects.filter(opened_at__isnull=False).count()

    daily_rows = (
        AttendanceRecord.objects.filter(scanned_at__gte=since)
        .annotate(day=TruncDate("scanned_at"))
        .values("day")
        .annotate(n=Count("id"))
        .order_by("day")
    )
    daily = {str(row["day"]): row["n"] for row in daily_rows}
    series = []
    for offset in range(since_days - 1, -1, -1):
        day = (timezone.localtime(now) - timedelta(days=offset)).date()
        series.append({"day": str(day), "count": daily.get(str(day), 0)})

    rejected = dict(
        AttendanceAttempt.objects.filter(accepted=False, created_at__gte=now - timedelta(days=30))
        .values_list("reason")
        .annotate(n=Count("id"))
    )

    records_by_course = dict(
        AttendanceRecord.objects.values_list("session__course_id").annotate(n=Count("id"))
    )
    course_rows = []
    courses = Course.objects.select_related("lecturer").annotate(
        enrolled=Count("enrollments", distinct=True),
        held=Count("sessions", filter=Q(sessions__opened_at__isnull=False), distinct=True),
    )
    for course in courses:
        course_rows.append(
            {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "lecturer": course.lecturer.display_name,
                "enrolled": course.enrolled,
                "sessions_held": course.held,
                "checkins": records_by_course.get(course.id, 0),
                "rate": _pct(records_by_course.get(course.id, 0), course.held * course.enrolled),
            }
        )
    course_rows.sort(key=lambda row: row["rate"], reverse=True)

    total_slots = sum(row["sessions_held"] * row["enrolled"] for row in course_rows)
    total_checkins = sum(row["checkins"] for row in course_rows)

    return {
        "users": {
            "admins": users_by_role.get("ADMIN", 0),
            "lecturers": users_by_role.get("LECTURER", 0),
            "students": users_by_role.get("STUDENT", 0),
        },
        "courses": len(course_rows),
        "sessions_held": sessions_held,
        "checkins": AttendanceRecord.objects.count(),
        "average_rate": _pct(total_checkins, total_slots),
        "daily_checkins": series,
        "rejected_attempts_30d": rejected,
        "courses_table": course_rows,
    }
