"""
Practitioners app models - Phase 2.
"""
import uuid

from django.db import models


class PractitionerStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    PENDING = "pending", "Pending Review"


class PractitionerType(models.TextChoices):
    DOCTOR = "doctor", "Doctor"
    NURSE = "nurse", "Nurse"
    LICENSED_PROFESSIONAL = "licensed_professional", "Licensed Professional"


class Practitioner(models.Model):
    """
    Medical practitioner affiliated with a clinic.

    SECURITY:
      - license_number, license_authority are INTERNAL - never expose to patients.
      - doctor ratings are not exposed to patients.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        related_name="practitioners",
    )

    # Practitioner type (doctor | nurse | licensed_professional)
    type = models.CharField(
        max_length=30,
        choices=PractitionerType.choices,
        default=PractitionerType.DOCTOR,
        db_index=True,
    )

    # Bilingual identity
    name_en = models.CharField(max_length=200, db_index=True)
    name_ar = models.CharField(max_length=200, blank=True, default="", db_index=True)
    title_en = models.CharField(max_length=100, blank=True, default="")
    title_ar = models.CharField(max_length=100, blank=True, default="")
    bio_en = models.TextField(blank=True, default="")
    bio_ar = models.TextField(blank=True, default="")
    speciality_en = models.CharField(max_length=200, blank=True, default="")
    speciality_ar = models.CharField(max_length=200, blank=True, default="")

    # License (INTERNAL - never expose to patients)
    license_number = models.CharField(max_length=100, blank=True, default="")
    license_authority = models.CharField(max_length=200, blank=True, default="")

    # Media integration
    avatar = models.URLField(blank=True, default="")
    media_asset = models.ForeignKey(
        "media.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="practitioners",
    )

    # Status & ordering
    status = models.CharField(
        max_length=20,
        choices=PractitionerStatus.choices,
        default=PractitionerStatus.ACTIVE,
        db_index=True,
    )
    display_order = models.PositiveIntegerField(default=0)

    # Timestamps / soft-delete
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "practitioners"
        verbose_name = "Practitioner"
        verbose_name_plural = "Practitioners"
        ordering = ["display_order", "name_en"]
        indexes = [
            models.Index(fields=["clinic", "status", "deleted_at"]),
            models.Index(fields=["type", "status"]),
        ]

    def __str__(self):
        return f"{self.name_en} ({self.clinic.name_en if self.clinic_id else 'No Clinic'})"

    @property
    def avatar_url(self) -> str:
        if self.avatar:
            return self.avatar
        if self.media_asset:
            return self.media_asset.url
        return ""
