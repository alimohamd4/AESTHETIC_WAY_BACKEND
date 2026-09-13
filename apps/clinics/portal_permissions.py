from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.models import ClinicRoleInClinic, UserRole
from apps.clinics.models import Clinic, ClinicStatus


def get_user_clinic(user) -> Clinic:
    """
    Returns the active Clinic for an authenticated clinic user.
    Raises NotAuthenticated if anonymous.
    Raises PermissionDenied if the user is a patient or has no active clinic assignment,
    or if the assigned clinic is suspended/deleted.
    """
    if not (user and user.is_authenticated):
        raise NotAuthenticated("Authentication required.")

    if not (user.is_clinic_user or user.is_super_admin):
        raise PermissionDenied("Only clinic staff or administrators can access the clinic portal.")

    membership = (
        user.clinic_memberships.filter(is_active=True)
        .select_related("clinic")
        .first()
    )

    # Super admin fallback if no explicit clinic membership exists
    if not membership and user.is_super_admin:
        clinic = Clinic.objects.filter(status=ClinicStatus.ACTIVE, deleted_at__isnull=True).first()
        if clinic:
            return clinic
        raise PermissionDenied("No clinic available for super admin portal access.")

    if not membership:
        raise PermissionDenied("No active clinic assignment found.")

    clinic = membership.clinic
    if clinic.status != ClinicStatus.ACTIVE or clinic.deleted_at is not None:
        raise PermissionDenied("CLINIC_SUSPENDED")

    return clinic


class IsClinicPortalAccess(BasePermission):
    """
    Verifies that the user is authenticated, has a clinic role or super_admin,
    and has an active membership in an active, non-suspended clinic.
    """

    message = "Only clinic staff or administrators with active clinic assignments can access the clinic portal."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if not (request.user.is_clinic_user or request.user.is_super_admin):
            return False

        try:
            clinic = get_user_clinic(request.user)
            request._portal_clinic = clinic
            return True
        except PermissionDenied as e:
            self.message = str(e)
            return False
        except NotAuthenticated:
            return False


class IsClinicAdminAccess(IsClinicPortalAccess):
    """
    Allows full clinic portal management access to clinic admins (or super admins).
    """

    message = "This operation requires a clinic administrator account."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        if request.user.is_super_admin or request.user.role == UserRole.CLINIC_ADMIN:
            return True

        membership = request.user.clinic_memberships.filter(is_active=True).first()
        return bool(membership and membership.role_in_clinic == ClinicRoleInClinic.ADMIN)
