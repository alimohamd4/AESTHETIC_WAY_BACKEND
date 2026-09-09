"""
Root conftest.py for AESTHETIC WAY test suite.
Provides shared fixtures used across all test modules.
"""
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import ClinicUser, PatientProfile, User, UserRole
from apps.accounts.services.sms import MockSmsProvider
from apps.clinics.models import Clinic


@pytest.fixture(autouse=True)
def reset_mock_sms():
    """Reset the MockSmsProvider message store before each test."""
    MockSmsProvider.reset()
    yield
    MockSmsProvider.reset()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache (LocMemCache) before each test to isolate OTP state."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def patient_user(db):
    """A verified patient user with PatientProfile."""
    user = User.objects.create_user(
        phone="+971501234567",
        full_name="Ahmed Patient",
        password="SecurePass123!",
        role=UserRole.PATIENT,
        is_verified=True,
    )
    return user


@pytest.fixture
def unverified_patient_user(db):
    """An unverified patient user (just registered, OTP not verified yet)."""
    user = User.objects.create_user(
        phone="+971501234568",
        full_name="New Patient",
        password="SecurePass123!",
        role=UserRole.PATIENT,
        is_verified=False,
    )
    return user


@pytest.fixture
def clinic(db):
    """A sample active clinic."""
    return Clinic.objects.create(name_en="Test Clinic", status="active")


@pytest.fixture
def clinic_admin_user(db, clinic):
    """A clinic admin user linked to the test clinic."""
    user = User.objects.create_user(
        phone="+971501234570",
        full_name="Clinic Admin",
        password="SecurePass123!",
        role=UserRole.CLINIC_ADMIN,
        is_verified=True,
    )
    ClinicUser.objects.create(user=user, clinic=clinic, role_in_clinic="admin", is_active=True)
    return user


@pytest.fixture
def clinic_staff_user(db, clinic):
    """A clinic staff user linked to the test clinic."""
    user = User.objects.create_user(
        phone="+971501234571",
        full_name="Clinic Staff",
        password="SecurePass123!",
        role=UserRole.CLINIC_STAFF,
        is_verified=True,
    )
    ClinicUser.objects.create(user=user, clinic=clinic, role_in_clinic="staff", is_active=True)
    return user


@pytest.fixture
def super_admin_user(db):
    """A super admin user."""
    return User.objects.create_user(
        phone="+971501234572",
        full_name="Super Admin",
        password="SecurePass123!",
        role=UserRole.SUPER_ADMIN,
        is_verified=True,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def authenticated_patient_client(api_client, patient_user):
    """API client authenticated as a verified patient."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(patient_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def authenticated_admin_client(api_client, clinic_admin_user):
    """API client authenticated as a clinic admin."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(clinic_admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


@pytest.fixture
def authenticated_super_admin_client(api_client, super_admin_user):
    """API client authenticated as a super admin."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(super_admin_user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client
