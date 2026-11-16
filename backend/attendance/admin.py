from django.contrib import admin

from .models import AttendanceAttempt, AttendanceRecord, Course, Enrollment, LectureSession


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "lecturer")
    search_fields = ("code", "name")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("course", "student", "enrolled_at")
    list_filter = ("course",)


@admin.register(LectureSession)
class LectureSessionAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "starts_at", "is_open")
    list_filter = ("course", "is_open")
    exclude = ("secret",)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("session", "student", "scanned_at", "distance_m")
    list_filter = ("session__course",)


@admin.register(AttendanceAttempt)
class AttendanceAttemptAdmin(admin.ModelAdmin):
    list_display = ("created_at", "student", "session", "reason", "distance_m")
    list_filter = ("reason", "accepted")
