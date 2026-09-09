"""
Django admin registration for accounts app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ClinicUser, OtpRecord, PatientProfile, PushToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["phone", "full_name", "email", "role", "is_verified", "is_active", "created_at"]
    list_filter = ["role", "is_verified", "is_active"]
    search_fields = ["phone", "full_name", "email"]
    ordering = ["-created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ("id", "phone", "password")}),
        ("Personal Info", {"fields": ("full_name", "email", "device_platform")}),
        ("Role & Status", {"fields": ("role", "is_verified", "is_active", "deleted_at")}),
        ("Permissions", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Timestamps", {"fields": ("created_at", "updated_at", "last_login_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("phone", "full_name", "password1", "password2", "role"),
        }),
    )


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "referral_code", "current_points", "total_successful_invites"]
    search_fields = ["user__phone", "user__full_name", "referral_code"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(ClinicUser)
class ClinicUserAdmin(admin.ModelAdmin):
    list_display = ["user", "clinic", "role_in_clinic", "is_active", "created_at"]
    list_filter = ["role_in_clinic", "is_active"]
    search_fields = ["user__phone", "user__full_name"]
    readonly_fields = ["id", "created_at"]


@admin.register(OtpRecord)
class OtpRecordAdmin(admin.ModelAdmin):
    list_display = ["phone", "purpose", "is_used", "expires_at", "created_at"]
    list_filter = ["purpose", "is_used"]
    search_fields = ["phone"]
    readonly_fields = ["id", "created_at"]


@admin.register(PushToken)
class PushTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "platform", "is_active", "created_at"]
    list_filter = ["platform", "is_active"]
