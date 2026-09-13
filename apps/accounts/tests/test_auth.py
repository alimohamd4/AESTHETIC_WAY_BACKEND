
"""
Comprehensive auth test suite for AESTHETIC WAY.
"""
import time

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import PatientProfile, User, UserRole
from apps.accounts.services.otp import (
    OTP_MAX_ATTEMPTS,
    OTP_TTL_SECONDS,
    _locked_key,
    _otp_key,
)
from apps.accounts.services.sms import MockSmsProvider
from apps.accounts.utils import hash_otp

REGISTER_URL = "/api/v1/auth/register/"
LOGIN_URL = "/api/v1/auth/login/"
VERIFY_OTP_URL = "/api/v1/auth/verify-otp/"
RESEND_OTP_URL = "/api/v1/auth/resend-otp/"
FORGOT_PASSWORD_URL = "/api/v1/auth/forgot-password/"
RESET_PASSWORD_URL = "/api/v1/auth/reset-password/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"


def _plant_otp(phone, purpose, code="123456"):
    code_hash = hash_otp(code)
    expires_at = int(time.time()) + OTP_TTL_SECONDS
    cache.set(_otp_key(phone, purpose), f"{code_hash}|{expires_at}", timeout=OTP_TTL_SECONDS)
    return code


def _plant_expired_otp(phone, purpose, code="999999"):
    code_hash = hash_otp(code)
    expires_at = int(time.time()) - 1
    cache.set(_otp_key(phone, purpose), f"{code_hash}|{expires_at}", timeout=1)
    return code


@pytest.mark.django_db
class TestRegistration:
    def setup_method(self):
        self.client = APIClient()

    def test_register_patient_success(self):
        resp = self.client.post(REGISTER_URL, {"full_name": "Sara Al Marzooqi", "phone": "+971501111111", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert "user_id" in data
        assert data["otp_purpose"] == "registration"
        user = User.objects.get(phone="+971501111111")
        assert user.role == UserRole.PATIENT
        assert user.is_verified is False
        assert PatientProfile.objects.filter(user=user).exists()
        assert user.patient_profile.referral_code.startswith("AW-")
        assert MockSmsProvider.last_otp("+971501111111") is not None

    def test_register_duplicate_phone_rejected(self):
        data = {"full_name": "A", "phone": "+971503333333", "password": "SecurePass123!"}
        self.client.post(REGISTER_URL, data, format="json")
        resp = self.client.post(REGISTER_URL, data, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in resp.json()

    def test_register_invalid_phone_rejected(self):
        resp = self.client.post(REGISTER_URL, {"full_name": "X", "phone": "not-a-phone", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_weak_password_rejected(self):
        resp = self.client.post(REGISTER_URL, {"full_name": "X", "phone": "+971504444444", "password": "123"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_missing_fields_rejected(self):
        resp = self.client.post(REGISTER_URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_register_role_always_patient(self):
        resp = self.client.post(REGISTER_URL, {"full_name": "Hacker", "phone": "+971507777777", "password": "SecurePass123!", "role": "super_admin"}, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        user = User.objects.get(phone="+971507777777")
        assert user.role == UserRole.PATIENT

    def test_register_with_valid_referral_code(self, db):
        inviter = User.objects.create_user(phone="+971509999999", full_name="Inviter", password="SecurePass123!", role=UserRole.PATIENT, is_verified=True)
        code = inviter.patient_profile.referral_code
        resp = self.client.post(REGISTER_URL, {"full_name": "Invited", "phone": "+971505555555", "password": "SecurePass123!", "referral_code": code}, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

    def test_register_with_invalid_referral_code_rejected(self):
        resp = self.client.post(REGISTER_URL, {"full_name": "X", "phone": "+971506666666", "password": "SecurePass123!", "referral_code": "INVALID"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestLogin:
    def setup_method(self):
        self.client = APIClient()

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        self.user = User.objects.create_user(phone="+971501234567", full_name="Ahmed Login", password="SecurePass123!", role=UserRole.PATIENT, is_verified=True)

    def test_login_with_phone_success(self):
        resp = self.client.post(LOGIN_URL, {"phone": "+971501234567", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data and "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["user"]["role"] == "patient"

    def test_login_with_email_success(self):
        self.user.email = "ahmed@test.com"
        self.user.save()
        resp = self.client.post(LOGIN_URL, {"phone": "ahmed@test.com", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_200_OK

    def test_login_wrong_password_rejected(self):
        resp = self.client.post(LOGIN_URL, {"phone": "+971501234567", "password": "WrongPass!"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_nonexistent_phone_rejected(self):
        resp = self.client.post(LOGIN_URL, {"phone": "+971500000001", "password": "SomePass!"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_deactivated_user_rejected(self):
        self.user.is_active = False
        self.user.save()
        resp = self.client.post(LOGIN_URL, {"phone": "+971501234567", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_with_identifier_phone_success(self):
        resp = self.client.post(LOGIN_URL, {"identifier": "+971501234567", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "access_token" in data and "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["user"]["role"] == "patient"

    def test_login_with_identifier_email_success(self):
        self.user.email = "ahmed@test.com"
        self.user.save()
        resp = self.client.post(LOGIN_URL, {"identifier": "ahmed@test.com", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["user"]["email"] == "ahmed@test.com"

    def test_login_missing_identifier_and_phone_rejected(self):
        resp = self.client.post(LOGIN_URL, {"password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_jwt_contains_correct_role(self):
        resp = self.client.post(LOGIN_URL, {"identifier": "+971501234567", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        import base64
        import json
        token = resp.json()["access_token"]
        payload_b64 = token.split(".")[1]
        padding = "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64 + padding))
        assert payload["role"] == "patient"
        assert payload["is_verified"] is True


@pytest.mark.django_db
class TestOtpVerification:
    def setup_method(self):
        self.client = APIClient()
        self.phone = "+971501234567"

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        self.user = User.objects.create_user(phone=self.phone, full_name="OTP User", password="SecurePass123!", role=UserRole.PATIENT, is_verified=False)

    def test_otp_verify_success_marks_verified(self):
        code = _plant_otp(self.phone, "registration")
        resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": code, "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert "access_token" in resp.json()
        self.user.refresh_from_db()
        assert self.user.is_verified is True

    def test_otp_wrong_code_returns_422(self):
        _plant_otp(self.phone, "registration")
        resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": "000000", "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.json()["error"]["code"] == "OTP_INVALID"

    def test_otp_expired_returns_422(self):
        _plant_expired_otp(self.phone, "registration")
        time.sleep(0.1)
        resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": "999999", "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_otp_brute_force_lockout(self):
        _plant_otp(self.phone, "registration", code="111111")
        for _ in range(OTP_MAX_ATTEMPTS - 1):
            resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": "000000", "purpose": "registration"}, format="json")
            assert resp.json()["error"]["code"] == "OTP_INVALID"
        # Final attempt triggers lockout
        resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": "000000", "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert resp.json()["error"]["code"] == "OTP_LOCKED"

    def test_otp_locked_correct_code_still_rejected(self):
        code = _plant_otp(self.phone, "registration")
        cache.set(_locked_key(self.phone, "registration"), 1, timeout=1800)
        resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": code, "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_otp_not_sent_returns_422(self):
        resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": "123456", "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.json()["error"]["code"] == "OTP_EXPIRED"

    def test_otp_password_reset_no_tokens(self):
        code = _plant_otp(self.phone, "password_reset")
        resp = self.client.post(VERIFY_OTP_URL, {"phone": self.phone, "otp_code": code, "purpose": "password_reset"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert "access_token" not in resp.json()


@pytest.mark.django_db
class TestOtpResend:
    def setup_method(self):
        self.client = APIClient()
        self.phone = "+971501111222"

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        User.objects.create_user(phone=self.phone, full_name="Resend User", password="SecurePass123!", role=UserRole.PATIENT)

    def test_resend_otp_success(self):
        resp = self.client.post(RESEND_OTP_URL, {"phone": self.phone, "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert MockSmsProvider.last_otp(self.phone) is not None

    def test_resend_rate_limited(self):
        self.client.post(RESEND_OTP_URL, {"phone": self.phone, "purpose": "registration"}, format="json")
        resp = self.client.post(RESEND_OTP_URL, {"phone": self.phone, "purpose": "registration"}, format="json")
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert resp.json()["error"]["code"] == "OTP_RATE_LIMIT"


@pytest.mark.django_db
class TestForgotPassword:
    def setup_method(self):
        self.client = APIClient()

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        self.user = User.objects.create_user(phone="+971508888888", full_name="Forgot User", password="SecurePass123!", role=UserRole.PATIENT, is_verified=True)

    def test_forgot_password_sends_otp(self):
        resp = self.client.post(FORGOT_PASSWORD_URL, {"phone": "+971508888888"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert MockSmsProvider.last_otp("+971508888888") is not None

    def test_forgot_password_inactive_user_rejected(self):
        self.user.is_active = False
        self.user.save()
        resp = self.client.post(FORGOT_PASSWORD_URL, {"phone": "+971508888888"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPasswordReset:
    def setup_method(self):
        self.client = APIClient()
        self.phone = "+971507654321"

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        self.user = User.objects.create_user(phone=self.phone, full_name="Reset User", password="OldPass123!", role=UserRole.PATIENT, is_verified=True)

    def test_reset_password_success(self):
        code = _plant_otp(self.phone, "password_reset")
        resp = self.client.post(RESET_PASSWORD_URL, {"phone": self.phone, "otp_code": code, "new_password": "NewSecurePass456!"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        self.user.refresh_from_db()
        assert self.user.check_password("NewSecurePass456!")

    def test_reset_password_wrong_otp(self):
        _plant_otp(self.phone, "password_reset", code="111111")
        resp = self.client.post(RESET_PASSWORD_URL, {"phone": self.phone, "otp_code": "000000", "new_password": "NewPass123!"}, format="json")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_reset_otp_one_time_use(self):
        code = _plant_otp(self.phone, "password_reset")
        self.client.post(RESET_PASSWORD_URL, {"phone": self.phone, "otp_code": code, "new_password": "NewPass123!"}, format="json")
        resp = self.client.post(RESET_PASSWORD_URL, {"phone": self.phone, "otp_code": code, "new_password": "AnotherPass789!"}, format="json")
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_reset_weak_password_rejected(self):
        code = _plant_otp(self.phone, "password_reset")
        resp = self.client.post(RESET_PASSWORD_URL, {"phone": self.phone, "otp_code": code, "new_password": "123"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestJwtAndRefresh:
    def setup_method(self):
        self.client = APIClient()

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        self.user = User.objects.create_user(phone="+971501111333", full_name="JWT Test", password="SecurePass123!", role=UserRole.PATIENT, is_verified=True)

    def _login(self):
        resp = self.client.post(LOGIN_URL, {"phone": "+971501111333", "password": "SecurePass123!"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()

    def test_refresh_returns_new_access_token(self):
        tokens = self._login()
        resp = self.client.post(REFRESH_URL, {"refresh": tokens["refresh_token"]}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["access_token"] != tokens["access_token"]

    def test_refresh_token_rotation_blacklists_old(self):
        tokens = self._login()
        self.client.post(REFRESH_URL, {"refresh": tokens["refresh_token"]}, format="json")
        resp = self.client.post(REFRESH_URL, {"refresh": tokens["refresh_token"]}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_refresh_token_rejected(self):
        resp = self.client.post(REFRESH_URL, {"refresh": "garbage.token.here"}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_access_token_grants_me(self):
        tokens = self._login()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
        assert self.client.get(ME_URL).status_code == status.HTTP_200_OK

    def test_expired_token_rejected(self):
        from datetime import timedelta

        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(token)}")
        assert self.client.get(ME_URL).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestLogout:
    def setup_method(self):
        self.client = APIClient()

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        self.user = User.objects.create_user(phone="+971501234999", full_name="Logout Test", password="SecurePass123!", role=UserRole.PATIENT, is_verified=True)
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.refresh_token = str(refresh)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_logout_success(self):
        resp = self.client.post(LOGOUT_URL, {"refresh_token": self.refresh_token}, format="json")
        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_logout_blacklists_refresh_token(self):
        self.client.post(LOGOUT_URL, {"refresh_token": self.refresh_token}, format="json")
        self.client.credentials()
        resp = self.client.post(REFRESH_URL, {"refresh": self.refresh_token}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_missing_token_returns_400(self):
        resp = self.client.post(LOGOUT_URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_unauthenticated_returns_401(self):
        resp = APIClient().post(LOGOUT_URL, {"refresh_token": self.refresh_token}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestMeEndpoint:
    def setup_method(self):
        self.client = APIClient()

    @pytest.fixture(autouse=True)
    def setup_user(self, db):
        self.user = User.objects.create_user(phone="+971501234888", full_name="Me User", email="me@test.com", password="SecurePass123!", role=UserRole.PATIENT, is_verified=True)
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

    def test_me_returns_correct_data(self):
        resp = self.client.get(ME_URL)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["phone"] == "+971501234888"
        assert data["role"] == "patient"
        assert data["is_verified"] is True

    def test_me_unauthenticated_returns_401(self):
        assert APIClient().get(ME_URL).status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_no_password_in_response(self):
        resp = self.client.get(ME_URL)
        assert "password" not in resp.content.decode()

    def test_me_patch_updates_name(self):
        resp = self.client.patch(ME_URL, {"full_name": "Updated Name"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        self.user.refresh_from_db()
        assert self.user.full_name == "Updated Name"

    def test_me_patch_cannot_change_role(self):
        self.client.patch(ME_URL, {"role": "super_admin"}, format="json")
        self.user.refresh_from_db()
        assert self.user.role == "patient"


@pytest.mark.django_db
class TestRolePermissions:
    def test_is_clinic_admin_rejects_staff(self, clinic_staff_user):
        from unittest.mock import MagicMock

        from core.permissions import IsClinicAdmin
        perm = IsClinicAdmin()
        req = MagicMock()
        req.user = clinic_staff_user
        assert not perm.has_permission(req, None)

    def test_is_super_admin_rejects_patient(self, patient_user):
        from unittest.mock import MagicMock

        from core.permissions import IsSuperAdmin
        perm = IsSuperAdmin()
        req = MagicMock()
        req.user = patient_user
        assert not perm.has_permission(req, None)

    def test_is_clinic_scoped_rejects_inactive_membership(self, db, clinic_admin_user, clinic):
        from unittest.mock import MagicMock

        from apps.accounts.models import ClinicUser
        from core.permissions import IsClinicScoped
        ClinicUser.objects.filter(user=clinic_admin_user, clinic=clinic).update(is_active=False)
        perm = IsClinicScoped()
        req = MagicMock()
        req.user = clinic_admin_user
        req.user._jwt_clinic_id = str(clinic.id)
        assert not perm.has_permission(req, None)


@pytest.mark.django_db
class TestHealthCheck:
    def test_returns_200_healthy(self):
        resp = APIClient().get("/api/v1/health/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["status"] == "healthy"

    def test_no_auth_required(self):
        assert APIClient().get("/api/v1/health/").status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestErrorFormat:
    def test_validation_error_envelope(self):
        resp = APIClient().post(REGISTER_URL, {}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_auth_error_envelope(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.here")
        resp = client.get(ME_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in resp.json()
