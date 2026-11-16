from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    """Base class: grants access to authenticated users with an allowed role."""

    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsAdminRole(HasRole):
    allowed_roles = ("ADMIN",)


class IsStudentRole(HasRole):
    allowed_roles = ("STUDENT",)


class IsAdminOrLecturer(HasRole):
    allowed_roles = ("ADMIN", "LECTURER")
