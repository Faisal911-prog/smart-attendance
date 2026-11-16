from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.core.validators import RegexValidator
from django.db import models

NEPTUN_VALIDATOR = RegexValidator(
    regex=r"^[A-Z0-9]{6}$",
    message="The institutional student code must be exactly 6 letters or digits (e.g. ABC123).",
)


class UserManager(DjangoUserManager):
    """Makes ``createsuperuser`` produce an application administrator."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "ADMIN")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """Single user table with a role column (Admin, Lecturer or Student)."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        LECTURER = "LECTURER", "Lecturer"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.STUDENT, db_index=True
    )
    # Institutional student identifier (the Neptun code at the University of
    # Debrecen). Unique, but optional for staff accounts.
    neptun_code = models.CharField(
        max_length=6, unique=True, null=True, blank=True, validators=[NEPTUN_VALIDATOR]
    )

    objects = UserManager()

    def save(self, *args, **kwargs):
        # Normalise: store NULL instead of an empty string so that the
        # unique constraint only applies to real codes.
        self.neptun_code = (self.neptun_code or "").strip().upper() or None
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username

    def __str__(self):
        return f"{self.display_name} ({self.role})"
