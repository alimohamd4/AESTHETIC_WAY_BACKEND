"""
AESTHETIC WAY - Custom DRF Permission Classes

Permission hierarchy (applied in order):
1. IsAuthenticated (built-in)
2. IsVerifiedUser
3. IsPatient / IsClinicUser / IsClinicAdmin / IsSuperAdmin
4. IsClinicScoped (DB re-validation)
5. IsActiveClinic (DB re-validation)
"""
from .roles import (  # noqa: F401
    IsActiveClinic,
    IsClinicAdmin,
    IsClinicScoped,
    IsClinicUser,
    IsPatient,
    IsSuperAdmin,
    IsVerifiedUser,
)
