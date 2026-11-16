"""Integration tests: the whole stack from HTTP request to database."""
import time

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from accounts.models import User
from attendance.models import AttendanceAttempt, AttendanceRecord, Course, Enrollment, LectureSession
from attendance.services import tokens

SITE = (47.5316, 21.6273)
PASSWORD = "Test-Passw0rd-123"


@override_settings(SECURE_SSL_REDIRECT=False)
class BaseAPITest(APITestCase):
    def setUp(self):
        cache.clear()  # reset the rate-limit counters
        self.admin = User.objects.create_user("admin", password=PASSWORD, role="ADMIN")
        self.lecturer = User.objects.create_user(
            "lect1", password=PASSWORD, role="LECTURER", first_name="Anna", last_name="Szabo"
        )
        self.other_lecturer = User.objects.create_user("lect2", password=PASSWORD, role="LECTURER")
        self.student = User.objects.create_user(
            "stud1", password=PASSWORD, role="STUDENT", neptun_code="STU001", first_name="Bence", last_name="Kiss"
        )
        self.outsider = User.objects.create_user(
            "stud2", password=PASSWORD, role="STUDENT", neptun_code="STU002"
        )
        self.course = Course.objects.create(code="INF101", name="Programming", lecturer=self.lecturer)
        Enrollment.objects.create(course=self.course, student=self.student)
        self.session = LectureSession.objects.create(
            course=self.course,
            title="Week 1",
            starts_at="2030-01-01T10:00:00Z",
            ends_at="2099-01-01T12:00:00Z",
            latitude=SITE[0],
            longitude=SITE[1],
            radius_m=100,
            qr_interval_seconds=30,
        )
        self.session.refresh_from_db()  # turn the ISO strings above into datetimes

    # helpers -----------------------------------------------------------
    def login_as(self, user):
        self.client.force_authenticate(user)

    def open_session(self):
        self.session.open()
        self.session.save()

    def token(self, now=None):
        return tokens.make_token(self.session.secret, self.session.id, 30, now)

    def scan(self, token=None, lat=SITE[0], lon=SITE[1], accuracy=10):
        return self.client.post(
            "/api/attendance/scan/",
            {"token": token or self.token(), "latitude": lat, "longitude": lon, "accuracy": accuracy},
            format="json",
        )


class AuthenticationTests(BaseAPITest):
    def test_login_returns_tokens_and_profile(self):
        response = self.client.post("/api/auth/login/", {"username": "stud1", "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["role"], "STUDENT")

    def test_wrong_password_is_rejected(self):
        response = self.client.post("/api/auth/login/", {"username": "stud1", "password": "nope"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoint_requires_token(self):
        self.assertEqual(self.client.get("/api/courses/").status_code, 401)

    def test_jwt_grants_access(self):
        login = self.client.post("/api/auth/login/", {"username": "lect1", "password": PASSWORD}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        self.assertEqual(self.client.get("/api/courses/").status_code, 200)

    def test_logout_blacklists_refresh_token(self):
        login = self.client.post("/api/auth/login/", {"username": "stud1", "password": PASSWORD}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        out = self.client.post("/api/auth/logout/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(out.status_code, 204)
        again = self.client.post("/api/auth/refresh/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(again.status_code, 401)

    def test_login_is_rate_limited(self):
        codes = [
            self.client.post("/api/auth/login/", {"username": "stud1", "password": "bad"}, format="json").status_code
            for _ in range(12)
        ]
        self.assertIn(429, codes)


class AuthorisationTests(BaseAPITest):
    def test_student_cannot_create_course(self):
        self.login_as(self.student)
        response = self.client.post("/api/courses/", {"code": "X1", "name": "X"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_use_session_management(self):
        self.login_as(self.student)
        self.assertEqual(self.client.get("/api/sessions/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/sessions/{self.session.id}/qr/").status_code, 403)

    def test_lecturer_sees_only_own_courses(self):
        Course.objects.create(code="INF999", name="Other", lecturer=self.other_lecturer)
        self.login_as(self.lecturer)
        codes = [c["code"] for c in self.client.get("/api/courses/").data]
        self.assertEqual(codes, ["INF101"])

    def test_lecturer_cannot_open_foreign_session(self):
        self.login_as(self.other_lecturer)
        self.assertEqual(self.client.post(f"/api/sessions/{self.session.id}/open/").status_code, 404)

    def test_student_sees_only_enrolled_courses(self):
        self.login_as(self.outsider)
        self.assertEqual(self.client.get("/api/courses/").data, [])

    def test_only_admin_can_manage_users(self):
        self.login_as(self.lecturer)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.login_as(self.admin)
        self.assertEqual(self.client.get("/api/users/").status_code, 200)

    def test_admin_creates_student_with_code(self):
        self.login_as(self.admin)
        response = self.client.post(
            "/api/users/",
            {"username": "new1", "password": "Very-Str0ng-pass", "role": "STUDENT", "neptun_code": "abc123"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.get(username="new1").neptun_code, "ABC123")

    def test_student_account_requires_code(self):
        self.login_as(self.admin)
        response = self.client.post(
            "/api/users/", {"username": "new2", "password": "Very-Str0ng-pass", "role": "STUDENT"}, format="json"
        )
        self.assertEqual(response.status_code, 400)


class CheckInTests(BaseAPITest):
    def test_successful_check_in(self):
        self.open_session()
        self.login_as(self.student)
        response = self.scan()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(AttendanceRecord.objects.filter(session=self.session, student=self.student).count(), 1)
        self.assertTrue(AttendanceAttempt.objects.filter(accepted=True, reason="OK").exists())

    def test_second_check_in_is_a_conflict(self):
        self.open_session()
        self.login_as(self.student)
        self.assertEqual(self.scan().status_code, 201)
        second = self.scan()
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.data["code"], "ALREADY_RECORDED")
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_outside_geofence_is_rejected_and_logged(self):
        self.open_session()
        self.login_as(self.student)
        response = self.scan(lat=SITE[0] + 0.01)  # about 1.1 km away
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "OUT_OF_RANGE")
        self.assertEqual(AttendanceRecord.objects.count(), 0)
        attempt = AttendanceAttempt.objects.get()
        self.assertFalse(attempt.accepted)
        self.assertGreater(attempt.distance_m, 1000)

    def test_imprecise_location_is_rejected(self):
        self.open_session()
        self.login_as(self.student)
        response = self.scan(accuracy=500)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "LOW_ACCURACY")

    def test_expired_token_is_rejected(self):
        self.open_session()
        self.login_as(self.student)
        response = self.scan(token=self.token(now=time.time() - 5 * 30))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "EXPIRED_TOKEN")

    def test_previous_window_still_accepted(self):
        self.open_session()
        self.login_as(self.student)
        response = self.scan(token=self.token(now=time.time() - 30))
        self.assertEqual(response.status_code, 201, response.data)

    def test_forged_token_is_rejected(self):
        self.open_session()
        self.login_as(self.student)
        forged = tokens.make_token("f" * 64, self.session.id, 30)
        response = self.scan(token=forged)
        self.assertEqual(response.data["code"], "INVALID_TOKEN")

    def test_garbage_token_is_rejected(self):
        self.open_session()
        self.login_as(self.student)
        self.assertEqual(self.scan(token="not-a-token").data["code"], "INVALID_TOKEN")

    def test_token_for_unknown_session_is_rejected(self):
        self.open_session()
        self.login_as(self.student)
        token = tokens.make_token(self.session.secret, 99999, 30)
        self.assertEqual(self.scan(token=token).data["code"], "INVALID_TOKEN")

    def test_closed_session_rejects_check_in(self):
        self.login_as(self.student)  # session was never opened
        response = self.scan()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "SESSION_CLOSED")

    def test_unenrolled_student_is_rejected(self):
        self.open_session()
        self.login_as(self.outsider)
        response = self.scan()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["code"], "NOT_ENROLLED")

    def test_lecturer_cannot_check_in(self):
        self.open_session()
        self.login_as(self.lecturer)
        self.assertEqual(self.scan().status_code, 403)

    def test_invalid_numbers_are_rejected_by_validation(self):
        self.open_session()
        self.login_as(self.student)
        self.assertEqual(self.scan(lat=123).status_code, 400)
        self.assertEqual(self.scan(accuracy="nan").status_code, 400)

    def test_scan_is_rate_limited(self):
        self.open_session()
        self.login_as(self.student)
        codes = [self.scan(token="x.y.z").status_code for _ in range(25)]
        self.assertIn(429, codes)


class SessionManagementTests(BaseAPITest):
    def test_lecturer_creates_session_and_opens_it(self):
        self.login_as(self.lecturer)
        payload = {
            "course": self.course.id,
            "title": "Week 2",
            "starts_at": "2030-02-01T10:00:00Z",
            "ends_at": "2099-02-01T11:30:00Z",
            "latitude": SITE[0],
            "longitude": SITE[1],
            "radius_m": 80,
            "qr_interval_seconds": 20,
        }
        created = self.client.post("/api/sessions/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertNotIn("secret", created.data)
        opened = self.client.post(f"/api/sessions/{created.data['id']}/open/")
        self.assertEqual(opened.status_code, 200)
        self.assertTrue(opened.data["is_open"])

    def test_lecturer_cannot_create_session_for_foreign_course(self):
        foreign = Course.objects.create(code="INF999", name="Other", lecturer=self.other_lecturer)
        self.login_as(self.lecturer)
        response = self.client.post(
            "/api/sessions/",
            {
                "course": foreign.id,
                "title": "x",
                "starts_at": "2030-02-01T10:00:00Z",
                "ends_at": "2030-02-01T11:00:00Z",
                "latitude": 1,
                "longitude": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_end_must_be_after_start(self):
        self.login_as(self.lecturer)
        response = self.client.post(
            "/api/sessions/",
            {
                "course": self.course.id,
                "title": "x",
                "starts_at": "2030-02-01T12:00:00Z",
                "ends_at": "2030-02-01T11:00:00Z",
                "latitude": 1,
                "longitude": 1,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_qr_endpoint_requires_open_session(self):
        self.login_as(self.lecturer)
        self.assertEqual(self.client.get(f"/api/sessions/{self.session.id}/qr/").status_code, 409)

    def test_qr_endpoint_returns_valid_token_and_image(self):
        self.open_session()
        self.login_as(self.lecturer)
        response = self.client.get(f"/api/sessions/{self.session.id}/qr/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["image"].startswith("data:image/png;base64,"))
        self.assertIn(response.data["token"], response.data["url"])
        parsed = tokens.parse_token(response.data["token"])
        tokens.verify_token(self.session.secret, parsed, 30)  # must not raise

    def test_attendance_roster_and_csv_export(self):
        self.open_session()
        self.login_as(self.student)
        self.assertEqual(self.scan().status_code, 201)
        self.login_as(self.lecturer)
        roster = self.client.get(f"/api/sessions/{self.session.id}/attendance/")
        self.assertEqual(roster.data["present"], 1)
        self.assertEqual(roster.data["enrolled"], 1)
        export = self.client.get(f"/api/sessions/{self.session.id}/export/")
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export["Content-Type"])
        self.assertIn("STU001", export.content.decode("utf-8"))

    def test_csv_export_neutralises_formulas(self):
        evil = User.objects.create_user(
            "evil", password=PASSWORD, role="STUDENT", neptun_code="EVL001", first_name="=HYPERLINK(1)"
        )
        Enrollment.objects.create(course=self.course, student=evil)
        self.login_as(self.lecturer)
        export = self.client.get(f"/api/sessions/{self.session.id}/export/")
        self.assertIn("'=HYPERLINK", export.content.decode("utf-8"))

    def test_bulk_enrolment_by_codes(self):
        self.login_as(self.lecturer)
        response = self.client.post(
            f"/api/courses/{self.course.id}/students/",
            {"neptun_codes": ["stu002", "STU001", "ZZZ999"]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["added"], 1)
        self.assertEqual(response.data["already_enrolled"], ["STU001"])
        self.assertEqual(response.data["unknown"], ["ZZZ999"])


class AnalyticsTests(BaseAPITest):
    def test_course_analytics_after_check_in(self):
        self.open_session()
        self.login_as(self.student)
        self.scan()
        self.scan(lat=SITE[0] + 0.01)  # rejected duplicate (already recorded)
        self.login_as(self.lecturer)
        data = self.client.get(f"/api/courses/{self.course.id}/analytics/").data
        self.assertEqual(data["sessions_held"], 1)
        self.assertEqual(data["enrolled"], 1)
        self.assertEqual(data["average_rate"], 100.0)
        self.assertEqual(data["students"][0]["present"], 1)

    def test_student_dashboard(self):
        self.open_session()
        self.login_as(self.student)
        self.scan()
        data = self.client.get("/api/attendance/my/").data
        self.assertEqual(data["courses"][0]["attended"], 1)
        self.assertEqual(data["courses"][0]["rate"], 100.0)
        self.assertTrue(data["open_sessions"][0]["checked_in"])

    def test_admin_overview(self):
        self.open_session()
        self.login_as(self.student)
        self.scan()
        self.login_as(self.admin)
        data = self.client.get("/api/analytics/overview/").data
        self.assertEqual(data["users"]["students"], 2)
        self.assertEqual(data["checkins"], 1)
        self.assertEqual(len(data["daily_checkins"]), 14)

    def test_overview_forbidden_for_lecturer(self):
        self.login_as(self.lecturer)
        self.assertEqual(self.client.get("/api/analytics/overview/").status_code, 403)
