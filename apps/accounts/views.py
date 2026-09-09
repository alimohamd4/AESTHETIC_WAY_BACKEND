"""
Auth views for AESTHETIC WAY API.

Endpoints:
  POST /auth/register/        - Patient registration
  POST /auth/login/           - Login (phone or email)
  POST /auth/verify-otp/      - OTP verification
  POST /auth/resend-otp/      - Resend OTP
  POST /auth/forgot-password/ - Request password reset OTP
  POST /auth/reset-password/  - Reset password with OTP
  POST /auth/refresh/         - Refresh access token
  POST /auth/logout/          - Logout (blacklist refresh token)
  GET  /auth/me/              - Current user profile

Security:
  - Role is ALWAYS sourced from the database, never from client input.
  - OTP codes generated server-side, never hardcoded.
  - Login rate-limiting via DRF throttle classes.
  - IP address forwarded to OTP service for anti-enumeration.
"""
import logging

from django.contrib.auth import update_session_auth_hash
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User, UserRole
from .serializers import (
    CustomTokenObtainPairSerializer,
    ForgotPasswordSerializer,
    OtpResendSerializer,
    OtpVerifySerializer,
    ResetPasswordSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)
from .services.otp import (
    OtpError,
    OtpExpiredError,
    OtpInvalidError,
    OtpIpLimitError,
    OtpLockedError,
    OtpNotFoundError,
    OtpRateLimitError,
    OtpService,
)

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str:
    """Extract client IP from request, respecting X-Forwarded-For header."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _otp_error_response(exc: OtpError) -> Response:
    """Convert an OtpError into a standardized error response."""
    status_map = {
        "OTP_RATE_LIMIT": status.HTTP_429_TOO_MANY_REQUESTS,
        "OTP_LOCKED": status.HTTP_429_TOO_MANY_REQUESTS,
        "OTP_IP_RATE_LIMIT": status.HTTP_429_TOO_MANY_REQUESTS,
        "OTP_EXPIRED": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "OTP_INVALID": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "OTP_NOT_FOUND": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "OTP_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
    }
    http_status = status_map.get(exc.code, status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response(
        {"error": {"code": exc.code, "message": str(exc)}},
        status=http_status,
    )


# --- Registration --------------------------------------------------------------

@extend_schema(
    tags=["Auth"],
    summary="Register a new patient account",
    description=(
        "Creates a patient account and sends an OTP to the provided phone number. "
        "The account is not usable until OTP verification is complete."
    ),
    responses={
        201: OpenApiResponse(description="Account created; OTP sent"),
        422: OpenApiResponse(description="Validation error"),
        429: OpenApiResponse(description="Rate limit exceeded"),
    },
)
class RegisterView(APIView):
    """POST /auth/register/ � Patient registration."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "register"

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        pending_referral = getattr(user, "_pending_referral_code", None)

        # Send OTP
        try:
            result = OtpService.send_otp(user.phone, "registration")
        except OtpRateLimitError as exc:
            # User was just created but OTP rate limit hit (unlikely on first request)
            return _otp_error_response(exc)

        return Response(
            {
                "user_id": str(user.id),
                "message": "Account created. Please verify your phone number.",
                "otp_purpose": "registration",
                "expires_in": result["expires_in"],
            },
            status=status.HTTP_201_CREATED,
        )


# --- Login ---------------------------------------------------------------------

@extend_schema(
    tags=["Auth"],
    summary="Login with phone/email and password",
    responses={
        200: OpenApiResponse(description="JWT tokens issued"),
        401: OpenApiResponse(description="Invalid credentials"),
        403: OpenApiResponse(description="Account not verified or suspended"),
    },
)
class LoginView(TokenObtainPairView):
    """POST /auth/login/ � Returns JWT access + refresh token pair."""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception:
            raise

        user = serializer.user
        # Update last login
        User.objects.filter(pk=user.pk).update(last_login_at=timezone.now())

        return Response(
            {
                "token_type": "Bearer",
                "access_token": serializer.validated_data["access"],
                "refresh_token": serializer.validated_data["refresh"],
                "expires_in": 3600,
                "user": serializer.validated_data["user"],
            },
            status=status.HTTP_200_OK,
        )


# --- OTP Verification ----------------------------------------------------------

@extend_schema(
    tags=["Auth"],
    summary="Verify OTP code",
    description=(
        "Verifies the OTP sent to the user''s phone. "
        "On success for ''registration'' purpose, marks the account as verified and returns JWT tokens."
    ),
)
class VerifyOtpView(APIView):
    """POST /auth/verify-otp/"""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp_verify"

    def post(self, request):
        serializer = OtpVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["otp_code"]
        purpose = serializer.validated_data["purpose"]
        ip = _get_client_ip(request)

        try:
            OtpService.verify_otp(phone, purpose, code, ip_address=ip)
        except OtpError as exc:
            return _otp_error_response(exc)

        # Fetch the user
        try:
            user = User.objects.get(phone=phone, deleted_at__isnull=True)
        except User.DoesNotExist:
            return Response(
                {"error": {"code": "USER_NOT_FOUND", "message": "User not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if purpose == "registration":
            # Mark user as verified
            if not user.is_verified:
                User.objects.filter(pk=user.pk).update(is_verified=True)
                user.is_verified = True

            # Process pending referral invite
            _process_referral_invite(user)

        if purpose in ("registration", "login"):
            # Issue JWT tokens
            refresh = RefreshToken.for_user(user)
            _add_custom_claims(refresh, user)

            return Response(
                {
                    "token_type": "Bearer",
                    "access_token": str(refresh.access_token),
                    "refresh_token": str(refresh),
                    "expires_in": 3600,
                    "user": UserProfileSerializer(user).data,
                },
                status=status.HTTP_200_OK,
            )

        # password_reset purpose � just confirm OTP was valid, no token issued
        return Response(
            {"message": "OTP verified. You may now reset your password."},
            status=status.HTTP_200_OK,
        )


def _add_custom_claims(token: RefreshToken, user: User) -> None:
    """Add custom claims to both access and refresh tokens."""
    token["role"] = user.role
    token["is_verified"] = user.is_verified
    token["full_name"] = user.full_name

    clinic_id = None
    if user.role in (UserRole.CLINIC_STAFF, UserRole.CLINIC_ADMIN):
        from apps.accounts.models import ClinicUser
        membership = ClinicUser.objects.filter(user=user, is_active=True).first()
        if membership:
            clinic_id = str(membership.clinic_id)
    token["clinic_id"] = clinic_id


def _process_referral_invite(user: User) -> None:
    """
    Record a referral invite if the user registered with a referral code.
    The code is stored in their PatientProfile.referral_code note during registration.
    (Full referral reward logic is implemented in Phase 4.)
    """
    pass  # Phase 4 implementation


# --- OTP Resend ----------------------------------------------------------------

@extend_schema(tags=["Auth"], summary="Resend OTP")
class ResendOtpView(APIView):
    """POST /auth/resend-otp/"""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "otp_resend"

    def post(self, request):
        serializer = OtpResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        purpose = serializer.validated_data["purpose"]

        try:
            result = OtpService.send_otp(phone, purpose)
        except OtpRateLimitError as exc:
            return _otp_error_response(exc)

        return Response(
            {
                "message": "A new OTP has been sent to your phone.",
                "expires_in": result["expires_in"],
                "resend_cooldown": result["resend_cooldown"],
            },
            status=status.HTTP_200_OK,
        )


# --- Forgot Password -----------------------------------------------------------

@extend_schema(tags=["Auth"], summary="Request password reset OTP")
class ForgotPasswordView(APIView):
    """POST /auth/forgot-password/"""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "forgot_password"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]

        try:
            OtpService.send_otp(phone, "password_reset")
        except OtpRateLimitError as exc:
            return _otp_error_response(exc)

        return Response(
            {"message": "If a matching account was found, an OTP has been sent."},
            status=status.HTTP_200_OK,
        )


# --- Reset Password ------------------------------------------------------------

@extend_schema(tags=["Auth"], summary="Reset password using OTP")
class ResetPasswordView(APIView):
    """POST /auth/reset-password/"""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data["phone"]
        code = serializer.validated_data["otp_code"]
        new_password = serializer.validated_data["new_password"]
        ip = _get_client_ip(request)

        # Verify OTP
        try:
            OtpService.verify_otp(phone, "password_reset", code, ip_address=ip)
        except OtpError as exc:
            return _otp_error_response(exc)

        # Update password
        try:
            user = User.objects.get(phone=phone, deleted_at__isnull=True, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"error": {"code": "USER_NOT_FOUND", "message": "User not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])

        logger.info("Password reset completed for user %s", user.id)
        return Response(
            {"message": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


# --- Token Refresh -------------------------------------------------------------

@extend_schema(tags=["Auth"], summary="Refresh access token")
class RefreshView(TokenRefreshView):
    """POST /auth/refresh/ � Rotate refresh token and issue new access token."""

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0]) from exc

        return Response(
            {
                "token_type": "Bearer",
                "access_token": serializer.validated_data["access"],
                "refresh_token": serializer.validated_data.get("refresh", ""),
            },
            status=status.HTTP_200_OK,
        )


# --- Logout --------------------------------------------------------------------

@extend_schema(tags=["Auth"], summary="Logout � blacklist refresh token")
class LogoutView(APIView):
    """POST /auth/logout/ � Blacklists the provided refresh token."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh_token")
        if not refresh_token:
            return Response(
                {"error": {"code": "MISSING_TOKEN", "message": "refresh_token is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            return Response(
                {"error": {"code": "INVALID_TOKEN", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info("User %s logged out", request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Current User --------------------------------------------------------------

@extend_schema(tags=["Auth"], summary="Get current authenticated user")
class MeView(generics.RetrieveUpdateAPIView):
    """GET /auth/me/ � Returns authenticated user profile."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user
