from rest_framework.permissions import BasePermission
from apps.accounts.models import UserRole

class IsSuperAdmin(BasePermission):
    """
    Allows access only to super admin users.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.role == UserRole.SUPER_ADMIN
        )
