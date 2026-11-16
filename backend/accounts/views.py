from django.db.models import ProtectedError, Q
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .permissions import IsAdminRole
from .serializers import ChangePasswordSerializer, LoginSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    """POST username + password, receive access/refresh JWT and the profile."""

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class LogoutView(APIView):
    """Blacklists the refresh token so it cannot be used again."""

    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response({"detail": "The refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password changed."})


class UserViewSet(viewsets.ModelViewSet):
    """User administration (administrators only)."""

    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        queryset = User.objects.all().order_by("role", "last_name", "first_name", "username")
        role = self.request.query_params.get("role")
        if role in User.Role.values:
            queryset = queryset.filter(role=role)
        search = self.request.query_params.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(neptun_code__icontains=search)
            )
        return queryset

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.pk == self.request.user.pk:
            new_role = serializer.validated_data.get("role", instance.role)
            new_active = serializer.validated_data.get("is_active", instance.is_active)
            if new_role != instance.role or not new_active:
                raise ValidationError("You cannot change the role of, or deactivate, your own account.")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response(
                {"detail": "You cannot delete your own account."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user.delete()
        except ProtectedError:
            return Response(
                {"detail": "This lecturer still owns courses. Reassign or delete them first."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
