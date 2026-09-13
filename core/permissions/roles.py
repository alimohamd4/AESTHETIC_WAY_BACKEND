"""
Role-based and scope-based permission classes for AESTHETIC WAY API.

ARCHITECTURE NOTE (from review):
- IsClinicScoped performs a DATABASE query, NOT a JWT claim comparison.
  JWT clinic_id is a routing hint only; the authoritative check is the clinic_users table.
- IsActiveClinic also performs a DATABASE query on every clinic portal request.
"""
import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class IsVerifiedUser(BasePermission):
    """
    Allows access only to users who have completed OTP verification.
    Checks user.is_verified (DB column, not JWT claim).
    """

    message = "Your account is not yet verified. Please verify your phone number."

    def has_permission(self, request, view):
        return (
            bool(request.user and request.user.is_authenticated)
            and request.user.is_verified
        )


class IsPatient(BasePermission):
    """Allows access only to patient-role users."""

    message = "This action is restricted to patient accounts."

    def has_permission(self, request, view):
        return (
            bool(request.user and request.user.is_authenticated)
            and request.user.role == "patient"
        )


class IsClinicUser(BasePermission):
    """Allows access to clinic_staff OR clinic_admin users."""

    message = "This action requires a clinic staff or admin account."

    def has_permission(self, request, view):
        return (
            bool(request.user and request.user.is_authenticated)
            and request.user.role in ("clinic_staff", "clinic_admin")
        )


class IsClinicAdmin(BasePermission):
    """Allows access only to clinic_admin users (not clinic_staff)."""

    message = "This action requires a clinic administrator account."

    def has_permission(self, request, view):
        return (
            bool(request.user and request.user.is_authenticated)
            and request.user.role == "clinic_admin"
        )


class IsSuperAdmin(BasePermission):
    """
    Allows access only to super_admin users or Django superusers.
    """

    message = "This action requires a super administrator account."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return bool(
            request.user.role == "super_admin"
            or getattr(request.user, "is_superuser", False)
        )


class IsClinicScoped(BasePermission):
    """
    Validates that the authenticated clinic user actually belongs to the clinic
    they are trying to access.

    CRITICAL: This is a DATABASE query, not a JWT claim comparison.
    JWT clinic_id is a routing hint only. This class re-validates against
    the clinic_users table (with is_active=True filter) on every request.

    Requires: request.user.role in ('clinic_staff', 'clinic_admin')
    """

    message = "You do not have access to this clinic."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.role not in ("clinic_staff", "clinic_admin"):
            return False

        # Import here to avoid circular imports at module load time
        from apps.accounts.models import ClinicUser

        clinic_id = getattr(request.user, "_jwt_clinic_id", None)
        if not clinic_id:
            return False

        return ClinicUser.objects.filter(
            user_id=request.user.id,
            clinic_id=clinic_id,
            is_active=True,
        ).exists()

    def has_object_permission(self, request, view, obj):
        """Object-level: verify resource belongs to same clinic."""
        clinic_id = getattr(request.user, "_jwt_clinic_id", None)
        if not clinic_id:
            return False

        resource_clinic_id = getattr(obj, "clinic_id", None)
        if resource_clinic_id is None:
            # Object has no clinic_id � allow if permission-level check passed
            return True

        return str(resource_clinic_id) == str(clinic_id)


class IsActiveClinic(BasePermission):
    """
    Ensures the clinic associated with the authenticated clinic user is active (not suspended).

    This is a DATABASE query on every clinic portal request.
    Returns 403 with CLINIC_SUSPENDED code when the clinic is suspended.
    """

    message = "CLINIC_SUSPENDED"

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        clinic_id = getattr(request.user, "_jwt_clinic_id", None)
        if not clinic_id:
            return False

        from apps.clinics.models import Clinic

        return Clinic.objects.filter(
            id=clinic_id,
            status="active",
            deleted_at__isnull=True,
        ).exists()
