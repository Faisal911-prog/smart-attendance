from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="display_name", read_only=True)
    password = serializers.CharField(
        write_only=True, required=False, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "role",
            "neptun_code",
            "is_active",
            "password",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "neptun_code": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def to_internal_value(self, data):
        # Accept lower-case student codes and normalise them.
        if hasattr(data, "get") and isinstance(data.get("neptun_code"), str):
            data = data.copy()
            data["neptun_code"] = data["neptun_code"].strip().upper()
        return super().to_internal_value(data)

    def validate_neptun_code(self, value):
        return value or None

    def validate_password(self, value):
        password_validation.validate_password(value, self.instance)
        return value

    def validate(self, attrs):
        instance = self.instance
        role = attrs.get("role", instance.role if instance else User.Role.STUDENT)
        neptun = attrs.get("neptun_code", instance.neptun_code if instance else None)
        if role == User.Role.STUDENT and not neptun:
            raise serializers.ValidationError({"neptun_code": "Required for student accounts."})
        if not instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A password is required."})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(TokenObtainPairSerializer):
    """Adds the role to the JWT claims and returns the user profile."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["name"] = user.display_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("The current password is incorrect.")
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value, self.context["request"].user)
        return value
