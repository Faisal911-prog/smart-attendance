from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Attendance system", {"fields": ("role", "neptun_code")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Attendance system", {"fields": ("role", "neptun_code")}),
    )
    list_display = ("username", "first_name", "last_name", "role", "neptun_code", "is_active")
    list_filter = ("role", "is_active")
    search_fields = ("username", "first_name", "last_name", "neptun_code")
