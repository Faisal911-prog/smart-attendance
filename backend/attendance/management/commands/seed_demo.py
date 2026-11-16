"""Create demo data: users, courses, enrolments, past sessions and check-ins.

Usage:  python manage.py seed_demo [--password SECRET] [--force]

The command refuses to run when DEBUG is off (to avoid creating well-known
accounts on a production system) unless --force is given.
"""
import os
import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import User
from attendance.models import AttendanceAttempt, AttendanceRecord, Course, Enrollment, LectureSession

# Placeholder coordinates in Debrecen -- replace them with the real room.
SITE_LAT, SITE_LON = 47.5316, 21.6273

LECTURERS = [("lecturer1", "Anna", "Szabo"), ("lecturer2", "Gabor", "Nagy")]
STUDENTS = [
    ("Bence", "Kiss"), ("Luca", "Toth"), ("Mate", "Horvath"), ("Zsofia", "Varga"),
    ("Daniel", "Molnar"), ("Eszter", "Farkas"), ("Adam", "Balogh"), ("Reka", "Papp"),
    ("Tamas", "Szilagyi"), ("Dora", "Juhasz"), ("Peter", "Lakatos"), ("Nora", "Simon"),
]
COURSES = [
    ("INF101", "Programming Fundamentals", "lecturer1", 12),
    ("INF202", "Web Development", "lecturer1", 12),
    ("INF305", "Database Systems", "lecturer2", 8),
]


class Command(BaseCommand):
    help = "Create demo users, courses, sessions and attendance records."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=os.environ.get("DEMO_PASSWORD", "Demo1234!"))
        parser.add_argument("--force", action="store_true", help="Allow running while DEBUG is off.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError("Refusing to create demo accounts while DEBUG is off (use --force).")
        if Course.objects.filter(code="INF101").exists():
            self.stdout.write("Demo data already exists - nothing to do.")
            return

        password = options["password"]
        rng = random.Random(42)
        now = timezone.now()

        admin, _ = User.objects.get_or_create(
            username="admin",
            defaults={"role": "ADMIN", "first_name": "System", "last_name": "Admin", "is_staff": True, "is_superuser": True},
        )
        admin.set_password(password)
        admin.save()

        lecturers = {}
        for username, first, last in LECTURERS:
            user, _ = User.objects.get_or_create(
                username=username, defaults={"role": "LECTURER", "first_name": first, "last_name": last}
            )
            user.set_password(password)
            user.save()
            lecturers[username] = user

        students = []
        for index, (first, last) in enumerate(STUDENTS, start=1):
            user, _ = User.objects.get_or_create(
                username=f"student{index}",
                defaults={
                    "role": "STUDENT",
                    "first_name": first,
                    "last_name": last,
                    "neptun_code": f"STU{index:03d}",
                },
            )
            user.set_password(password)
            user.save()
            students.append(user)

        for code, name, lecturer_username, count in COURSES:
            course = Course.objects.create(code=code, name=name, lecturer=lecturers[lecturer_username])
            enrolled = students[:count]
            Enrollment.objects.bulk_create([Enrollment(course=course, student=s) for s in enrolled])
            self._create_history(course, enrolled, rng, now)

        # A session for "today" that the lecturer can open during the demo.
        course = Course.objects.get(code="INF202")
        LectureSession.objects.create(
            course=course,
            title="Live demo lecture",
            starts_at=now,
            ends_at=now + timedelta(hours=2),
            latitude=SITE_LAT,
            longitude=SITE_LON,
            radius_m=150,
            qr_interval_seconds=30,
        )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(f"  admin      / {password}")
        self.stdout.write(f"  lecturer1  / {password}   (courses INF101, INF202)")
        self.stdout.write(f"  lecturer2  / {password}   (course INF305)")
        self.stdout.write(f"  student1..student{len(students)} / {password}   (codes STU001..STU{len(students):03d})")

    def _create_history(self, course, enrolled, rng, now):
        """Six weekly past sessions with varying attendance and a few rejected attempts."""
        for week in range(6, 0, -1):
            start = now - timedelta(weeks=week)
            session = LectureSession.objects.create(
                course=course,
                title=f"Week {7 - week}",
                starts_at=start,
                ends_at=start + timedelta(minutes=90),
                latitude=SITE_LAT,
                longitude=SITE_LON,
                radius_m=150,
                is_open=False,
                opened_at=start,
                closed_at=start + timedelta(minutes=90),
            )
            for student in enrolled:
                # Each student has a personal attendance habit between 45% and 100%.
                habit = 0.45 + 0.55 * ((student.id * 7 + course.id * 3) % 10) / 9
                if rng.random() < habit:
                    when = start + timedelta(minutes=rng.randint(1, 20))
                    distance = rng.uniform(5, 120)
                    record = AttendanceRecord.objects.create(
                        session=session,
                        student=student,
                        latitude=SITE_LAT,
                        longitude=SITE_LON,
                        accuracy_m=rng.uniform(5, 40),
                        distance_m=distance,
                    )
                    AttendanceRecord.objects.filter(pk=record.pk).update(scanned_at=when)
            if rng.random() < 0.6:
                student = rng.choice(enrolled)
                attempt = AttendanceAttempt.objects.create(
                    session=session,
                    student=student,
                    accepted=False,
                    reason="OUT_OF_RANGE",
                    latitude=SITE_LAT + 0.01,
                    longitude=SITE_LON,
                    accuracy_m=12.0,
                    distance_m=1112.0,
                )
                AttendanceAttempt.objects.filter(pk=attempt.pk).update(created_at=start + timedelta(minutes=5))
