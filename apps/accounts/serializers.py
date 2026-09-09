"""
Serializers for the accounts app.
Handles registration, login, OTP, password reset, and profile.
"""
import logging


from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User, UserRole
from .utils import normalize_phone

logger = logging.getLogger(__name__)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT token pair serializer.
    Adds user claims to the JWT payload: role, clinic_id, is_verified.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token["role"] = user.role
        token["is_verified"] = user.is_verified
        token["full_name"] = user.full_name

        # Add clinic_id for clinic users (routing hint � NOT the auth check)
        clinic_id = None
        if user.role in (UserRole.CLINIC_STAFF, UserRole.CLINIC_ADMIN):
            membership = user.clinic_memberships.filter(is_active=True).first()
            if membership:
                clinic_id = str(membership.clinic_id)
        token["clinic_id"] = clinic_id

        return token

    def validate(self, attrs):
        # Accept phone or email as identifier
        identifier = attrs.get(self.username_field, "")
        password = attrs.get("password", "")

        # Resolve identifier to User object
        user = None
        if "@" in identifier:
            try:
                candidate = User.objects.get(email=identifier, deleted_at__isnull=True)
                if candidate.check_password(password):
                    user = candidate
            except User.DoesNotExist:
                pass
        else:
            try:
                candidate = User.objects.get(phone=identifier, deleted_at__isnull=True)
                if candidate.check_password(password):
                    user = candidate
            except User.DoesNotExist:
                pass

        if not user:
            raise serializers.ValidationError(
                {"detail": "Invalid credentials. Please check your phone/email and password."},
                code="authentication_failed",
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "This account has been deactivated."},
                code="account_deactivated",
            )

        if user.deleted_at is not None:
            raise serializers.ValidationError(
                {"detail": "This account does not exist."},
                code="account_deleted",
            )

        self.user = user

        # Generate JWT tokens directly (do NOT call super().validate() — it would re-authenticate
        # via ModelBackend which doesn't support our custom phone/email lookup)
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        # Add custom claims via get_token
        refresh = self.__class__.get_token(user)

        data = {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserProfileSerializer(user).data,
        }
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for patient registration."""

    password = serializers.CharField(write_only=True, min_length=8)
    referral_code = serializers.CharField(required=False, allow_blank=True, max_length=30)

    class Meta:
        model = User
        fields = [
            "full_name",
            "phone",
            "email",
            "password",
            "referral_code",
            "device_platform",
        ]
        extra_kwargs = {
            "email": {"required": False, "allow_null": True},
            "device_platform": {"required": False, "allow_null": True},
        }

    def validate_phone(self, value):
        try:
            normalized = normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

        if User.objects.filter(phone=normalized, deleted_at__isnull=True).exists():
            raise serializers.ValidationError("An account with this phone number already exists.")
        return normalized

    def validate_email(self, value):
        if value and User.objects.filter(email=value, deleted_at__isnull=True).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value

    def validate_referral_code(self, value):
        if not value:
            return None
        from apps.accounts.models import PatientProfile
        if not PatientProfile.objects.filter(referral_code=value).exists():
            raise serializers.ValidationError("Invalid referral code.")
        return value

    def create(self, validated_data):
        referral_code = validated_data.pop("referral_code", None)
        password = validated_data.pop("password")
        user = User.objects.create_user(
            password=password,
            role=UserRole.PATIENT,
            **validated_data,
        )
        # Store referral code for post-OTP processing
        if referral_code:
            user._pending_referral_code = referral_code
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (GET /auth/me and login response)."""

    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "role",
            "is_verified",
            "device_platform",
            "created_at",
        ]
        read_only_fields = ["id", "role", "is_verified", "created_at"]


class OtpVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification."""

    phone = serializers.CharField(max_length=20)
    otp_code = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(choices=["registration", "login", "password_reset"])

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e


class OtpResendSerializer(serializers.Serializer):
    """Serializer for OTP resend requests."""

    phone = serializers.CharField(max_length=20)
    purpose = serializers.ChoiceField(choices=["registration", "login", "password_reset"])

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for forgot password request."""

    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        try:
            normalized = normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

        if not User.objects.filter(phone=normalized, deleted_at__isnull=True, is_active=True).exists():
            # Don't reveal whether the phone exists (security)
            raise serializers.ValidationError("No active account found with this phone number.")
        return normalized


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for password reset after OTP verification."""

    phone = serializers.CharField(max_length=20)
    otp_code = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=8)

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e)) from e

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages)) from e
        return value
