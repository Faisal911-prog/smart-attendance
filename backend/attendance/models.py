from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from .services import tokens


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    lecturer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="courses_taught",
        limit_choices_to={"role": "LECTURER"},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class Enrollment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
        limit_choices_to={"role": "STUDENT"},
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["course", "student"], name="unique_enrollment"),
        ]

    def __str__(self):
        return f"{self.student} in {self.course.code}"


class LectureSession(models.Model):
    """One lecture/seminar occasion for which attendance is collected."""

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=200)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    # Geofence: centre of the classroom and the accepted radius in metres.
    latitude = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])
    radius_m = models.PositiveIntegerField(
        default=100, validators=[MinValueValidator(10), MaxValueValidator(2000)]
    )

    # How often the QR code changes, in seconds.
    qr_interval_seconds = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(10), MaxValueValidator(300)]
    )
    # Secret used to sign the rotating QR tokens. Never exposed by the API.
    secret = models.CharField(max_length=64, default=tokens.new_secret, editable=False)

    is_open = models.BooleanField(default=False)
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at"]
        indexes = [models.Index(fields=["course", "starts_at"])]

    def __str__(self):
        return f"{self.course.code}: {self.title}"

    def is_accepting(self, now=None):
        """True while students may check in."""
        now = now or timezone.now()
        return self.is_open and now <= self.ends_at

    def open(self):
        self.is_open = True
        self.opened_at = self.opened_at or timezone.now()
        self.closed_at = None

    def close(self):
        self.is_open = False
        self.closed_at = timezone.now()


class AttendanceRecord(models.Model):
    """A successful check-in (at most one per student and session)."""

    session = models.ForeignKey(LectureSession, on_delete=models.CASCADE, related_name="records")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_records"
    )
    scanned_at = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy_m = models.FloatField()
    distance_m = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "student"], name="unique_attendance"),
        ]
        indexes = [models.Index(fields=["student", "scanned_at"])]

    def __str__(self):
        return f"{self.student} @ {self.session}"


class AttendanceAttempt(models.Model):
    """Audit log of every check-in attempt, accepted or rejected."""

    class Reason(models.TextChoices):
        OK = "OK", "Accepted"
        INVALID_TOKEN = "INVALID_TOKEN", "Invalid QR code"
        EXPIRED_TOKEN = "EXPIRED_TOKEN", "Expired QR code"
        SESSION_CLOSED = "SESSION_CLOSED", "Session closed"
        NOT_ENROLLED = "NOT_ENROLLED", "Not enrolled"
        ALREADY_RECORDED = "ALREADY_RECORDED", "Already recorded"
        OUT_OF_RANGE = "OUT_OF_RANGE", "Outside the allowed area"
        LOW_ACCURACY = "LOW_ACCURACY", "Location too imprecise"
        BAD_COORDINATES = "BAD_COORDINATES", "Invalid coordinates"

    session = models.ForeignKey(
        LectureSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="attempts"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendance_attempts"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    accepted = models.BooleanField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    accuracy_m = models.FloatField(null=True, blank=True)
    distance_m = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} {self.reason} at {self.created_at:%Y-%m-%d %H:%M:%S}"
