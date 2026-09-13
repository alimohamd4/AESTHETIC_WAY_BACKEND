"""
AESTHETIC WAY - Accounts Models

Entities:
- User: Custom AbstractBaseUser with UUID PK and role system
- PatientProfile: 1:1 extension for patient-specific referral data
- ClinicUser: M2M junction linking users to clinics (with role in clinic)
- OtpRecord: OTP audit trail (Redis is primary; DB is audit-only)
"""
import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

# --- Choices ------------------------------------------------------------------

class UserRole(models.TextChoices):
    PATIENT = "patient", "Patient"
    CLINIC_STAFF = "clinic_staff", "Clinic Staff"
    CLINIC_ADMIN = "clinic_admin", "Clinic Admin"
    SUPER_ADMIN = "super_admin", "Super Admin"


class DevicePlatform(models.TextChoices):
    IOS = "ios", "iOS"
    ANDROID = "android", "Android"
    WEB = "web", "Web"


class OtpPurpose(models.TextChoices):
    REGISTRATION = "registration", "Registration"
    LOGIN = "login", "Login"
    PASSWORD_RESET = "password_reset", "Password Reset"


class ClinicRoleInClinic(models.TextChoices):
    ADMIN = "admin", "Admin"
    STAFF = "staff", "Staff"


# --- User Manager -------------------------------------------------------------

class UserManager(BaseUserManager):
    """Custom manager for the User model."""

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("Phone number is required.")
        extra_fields.setdefault("role", UserRole.PATIENT)
        extra_fields.setdefault("is_active", True)
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("role", UserRole.SUPER_ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(phone, password, **extra_fields)


# --- User ---------------------------------------------------------------------

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for AESTHETIC WAY.

    Identity is phone-based (no username).
    Email is optional and unique when provided.
    Role system drives all authorization decisions.
    UUID primary key throughout.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(max_length=254, null=True, blank=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.PATIENT,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_verified = models.BooleanField(
        default=False,
        help_text="Set to True after successful OTP verification.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Allows access to Django admin interface.",
    )
    device_platform = models.CharField(
        max_length=10,
        choices=DevicePlatform.choices,
        null=True,
        blank=True,
    )
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=models.Q(email__isnull=False),
                name="unique_email_when_not_null",
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone}) [{self.role}]"

    @property
    def is_clinic_user(self):
        return self.role in (UserRole.CLINIC_STAFF, UserRole.CLINIC_ADMIN)

    @property
    def is_patient(self):
        return self.role == UserRole.PATIENT

    @property
    def is_super_admin(self):
        return self.role == UserRole.SUPER_ADMIN


# --- Patient Profile ----------------------------------------------------------

class PatientProfile(models.Model):
    """
    1:1 extension for patient users.
    Holds referral code, current point balance (cache), and milestone flags.

    CRITICAL: current_points is a materialized cache.
    Source of truth is referral_points_ledger SUM.
    milestone_*_awarded are display caches only � NOT the concurrency guard.
    The partial unique index on referral_points_ledger IS the guard.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="patient_profile",
    )
    referral_code = models.CharField(max_length=30, unique=True)
    current_points = models.PositiveIntegerField(default=0)
    total_successful_invites = models.PositiveIntegerField(default=0)
    # Milestone display cache (NOT the concurrency guard � see referral_points_ledger)
    milestone_20_awarded = models.BooleanField(default=False)
    milestone_35_awarded = models.BooleanField(default=False)
    milestone_50_awarded = models.BooleanField(default=False)
    referred_by_code = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "patient_profiles"
        verbose_name = "Patient Profile"
        verbose_name_plural = "Patient Profiles"
        indexes = [
            models.Index(fields=["referral_code"]),
            models.Index(fields=["current_points"]),
        ]

    def __str__(self):
        return f"Profile for {self.user.full_name} | Code: {self.referral_code}"


# --- Clinic User Junction -----------------------------------------------------

class ClinicUser(models.Model):
    """
    Junction table linking users to clinics.
    A user may be linked to one clinic in v1 (multi-clinic is v2).

    SECURITY: IsClinicScoped queries this table (with is_active=True) on every
    clinic portal request. Never trust JWT clinic_id claim alone.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clinic_memberships",
    )
    # FK to clinics.Clinic � defined as string ref to avoid circular import
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        related_name="clinic_users",
    )
    role_in_clinic = models.CharField(
        max_length=20,
        choices=ClinicRoleInClinic.choices,
        default=ClinicRoleInClinic.STAFF,
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Set to False to suspend access without deleting the record.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "clinic_users"
        verbose_name = "Clinic User"
        verbose_name_plural = "Clinic Users"
        unique_together = [("user", "clinic")]
        indexes = [
            models.Index(fields=["clinic", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.full_name} @ {self.clinic} [{self.role_in_clinic}]"


# --- OTP Record ---------------------------------------------------------------

class OtpRecord(models.Model):
    """
    OTP audit trail stored in the database.

    IMPORTANT: Redis is the PRIMARY verification authority.
    This table is written asynchronously for audit purposes ONLY.
    Never read this table to verify an OTP � use Redis.

    Rate limiting and attempt counting also live in Redis.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=20, db_index=True)
    purpose = models.CharField(max_length=30, choices=OtpPurpose.choices)
    # HMAC-SHA256 of the code � not bcrypt; fast enough for 6-digit codes
    code_hash = models.CharField(max_length=255)
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "otp_records"
        verbose_name = "OTP Record"
        verbose_name_plural = "OTP Records"
        indexes = [
            models.Index(fields=["phone", "purpose", "is_used"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"OTP for {self.phone} ({self.purpose}) used={self.is_used}"


# --- Push Tokens --------------------------------------------------------------

class PushToken(models.Model):
    """FCM / APNs device push tokens."""

    class Platform(models.TextChoices):
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="push_tokens",
    )
    token = models.TextField()
    platform = models.CharField(max_length=10, choices=Platform.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "push_tokens"
        verbose_name = "Push Token"
        verbose_name_plural = "Push Tokens"
        unique_together = [("user", "token")]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.platform} token for {self.user.full_name}"
