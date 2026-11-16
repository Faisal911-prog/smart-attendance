import math

from rest_framework import serializers

from accounts.models import User

from .models import Course, LectureSession


class CourseSerializer(serializers.ModelSerializer):
    lecturer_name = serializers.CharField(source="lecturer.display_name", read_only=True)
    student_count = serializers.SerializerMethodField()
    session_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "code",
            "name",
            "description",
            "lecturer",
            "lecturer_name",
            "student_count",
            "session_count",
            "created_at",
        ]
        read_only_fields = ["created_at"]
        extra_kwargs = {"lecturer": {"required": False}}

    def get_student_count(self, obj):
        value = getattr(obj, "student_count", None)
        return value if value is not None else obj.enrollments.count()

    def get_session_count(self, obj):
        value = getattr(obj, "session_count", None)
        return value if value is not None else obj.sessions.count()

    def validate_lecturer(self, value):
        if value.role != User.Role.LECTURER:
            raise serializers.ValidationError("The selected user is not a lecturer.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        if user.role == User.Role.LECTURER:
            attrs["lecturer"] = user  # lecturers can only manage their own courses
        elif not self.instance and "lecturer" not in attrs:
            raise serializers.ValidationError({"lecturer": "Choose the lecturer of the course."})
        return attrs


class LectureSessionSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.code", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    is_accepting = serializers.SerializerMethodField()
    present_count = serializers.SerializerMethodField()
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = LectureSession
        fields = [
            "id",
            "course",
            "course_code",
            "course_name",
            "title",
            "starts_at",
            "ends_at",
            "latitude",
            "longitude",
            "radius_m",
            "qr_interval_seconds",
            "is_open",
            "is_accepting",
            "opened_at",
            "closed_at",
            "present_count",
            "enrolled_count",
        ]
        read_only_fields = ["is_open", "opened_at", "closed_at"]

    def get_is_accepting(self, obj):
        return obj.is_accepting()

    def get_present_count(self, obj):
        value = getattr(obj, "present_count", None)
        return value if value is not None else obj.records.count()

    def get_enrolled_count(self, obj):
        value = getattr(obj, "enrolled_count", None)
        return value if value is not None else obj.course.enrollments.count()

    def validate_course(self, course):
        user = self.context["request"].user
        if user.role == User.Role.LECTURER and course.lecturer_id != user.id:
            raise serializers.ValidationError("You can only manage sessions of your own courses.")
        return course

    def validate(self, attrs):
        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({"ends_at": "The end time must be after the start time."})
        if self.instance and "course" in attrs and attrs["course"].pk != self.instance.course_id:
            raise serializers.ValidationError({"course": "A session cannot be moved to another course."})
        return attrs


class ScanSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=100)
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy = serializers.FloatField(min_value=0, max_value=100000)

    def validate(self, attrs):
        for field in ("latitude", "longitude", "accuracy"):
            if not math.isfinite(attrs[field]):
                raise serializers.ValidationError({field: "Must be a finite number."})
        return attrs


class EnrollSerializer(serializers.Serializer):
    neptun_codes = serializers.ListField(
        child=serializers.CharField(max_length=6), allow_empty=False, max_length=500
    )
