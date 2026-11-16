"""The check-in pipeline.

A student's request passes through the following gates, in this order. The
first failing gate rejects the request, and *every* attempt (accepted or not)
is written to the audit log.

1. QR token is well formed
2. the session named in the token exists
3. the token signature is authentic and fresh (rotating HMAC)
4. the session is open and has not ended
5. the student is enrolled in the course
6. the student has not already checked in
7. the reported location passes the geofence (valid, accurate, close enough)
"""
import time
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction

from ..models import AttendanceAttempt, AttendanceRecord, Enrollment, LectureSession
from . import geo, tokens

MESSAGES = {
    "INVALID_TOKEN": ("This QR code is not valid. Scan the code that is currently shown by your lecturer.", 400),
    "EXPIRED_TOKEN": ("This QR code has expired. Scan the code that is currently shown on the screen.", 400),
    "SESSION_CLOSED": ("Attendance for this session is closed.", 403),
    "NOT_ENROLLED": ("You are not enrolled in this course.", 403),
    "ALREADY_RECORDED": ("Your attendance for this session has already been recorded.", 409),
    "OUT_OF_RANGE": ("You appear to be too far from the lecture location.", 400),
    "LOW_ACCURACY": (
        "Your device reported a location that is too imprecise. Enable precise location, "
        "move closer to a window and try again.",
        400,
    ),
    "BAD_COORDINATES": ("The location data sent by your device is not valid.", 400),
}


class ScanRejected(Exception):
    def __init__(self, reason):
        self.reason = reason
        self.message, self.status = MESSAGES[reason]
        super().__init__(reason)


def process_scan(*, student, token, latitude, longitude, accuracy, now=None):
    """Validate a check-in and return the new ``AttendanceRecord``.

    ``now`` (epoch seconds) can be injected to make time-dependent behaviour
    testable. Raises ``ScanRejected`` when any gate fails.
    """
    now_ts = time.time() if now is None else now
    now_dt = datetime.fromtimestamp(now_ts, tz=dt_timezone.utc)
    config = settings.ATTENDANCE

    def reject(reason, session=None, distance=None):
        AttendanceAttempt.objects.create(
            session=session,
            student=student,
            accepted=False,
            reason=reason,
            latitude=latitude,
            longitude=longitude,
            accuracy_m=accuracy,
            distance_m=distance,
        )
        raise ScanRejected(reason)

    # 1-2. Token structure and session lookup
    try:
        parsed = tokens.parse_token(token)
    except tokens.TokenError:
        reject("INVALID_TOKEN")

    session = LectureSession.objects.select_related("course").filter(pk=parsed.session_id).first()
    if session is None:
        reject("INVALID_TOKEN")

    # 3. Signature and freshness
    try:
        tokens.verify_token(
            session.secret,
            parsed,
            session.qr_interval_seconds,
            grace_windows=config["QR_GRACE_WINDOWS"],
            now=now_ts,
        )
    except tokens.TokenError as exc:
        reject(exc.code, session)

    # 4. Session state
    if not session.is_accepting(now_dt):
        reject("SESSION_CLOSED", session)

    # 5. Enrolment
    if not Enrollment.objects.filter(course=session.course, student=student).exists():
        reject("NOT_ENROLLED", session)

    # 6. Duplicate check (the database constraint is the final guard below)
    if AttendanceRecord.objects.filter(session=session, student=student).exists():
        reject("ALREADY_RECORDED", session)

    # 7. Geofence
    check = geo.check_location(
        session.latitude,
        session.longitude,
        session.radius_m,
        latitude,
        longitude,
        accuracy,
        config["MAX_GPS_ACCURACY_M"],
    )
    if not check.ok:
        reject(check.reason, session, check.distance_m)

    try:
        with transaction.atomic():
            record = AttendanceRecord.objects.create(
                session=session,
                student=student,
                latitude=latitude,
                longitude=longitude,
                accuracy_m=accuracy,
                distance_m=check.distance_m,
            )
    except IntegrityError:
        # Two simultaneous requests: the unique constraint let only one through.
        reject("ALREADY_RECORDED", session)

    AttendanceAttempt.objects.create(
        session=session,
        student=student,
        accepted=True,
        reason="OK",
        latitude=latitude,
        longitude=longitude,
        accuracy_m=accuracy,
        distance_m=check.distance_m,
    )
    return record
