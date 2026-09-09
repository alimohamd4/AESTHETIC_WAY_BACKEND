"""
Practitioners app models - Phase 2.
"""
import uuid

from django.db import models


class PractitionerStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    PENDING = "pending", "Pending Review"


class Practitioner(models.Model):
    """
    Medical practitioner affiliated with a clinic.

    SECURITY:
      - license_number, license_authority are INTERNAL - never expose to patients.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        related_name="practitioners",
    )

    # Bilingual identity
    name_en = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True, default="")
    title_en = models.CharField(max_length=100, blank=True, default="")
    title_ar = models.CharField(max_length=100, blank=True, default="")
    bio_en = models.TextField(blank=True, default="")
    bio_ar = models.TextField(blank=True, default="")
    speciality_en = models.CharField(max_length=200, blank=True, default="")
    speciality_ar = models.CharField(max_length=200, blank=True, default="")

    # License (INTERNAL - never expose to patients)
    license_number = models.CharField(max_length=100, blank=True, default="")
    license_authority = models.CharField(max_length=200, blank=True, default="")

    # Media
    avatar = models.URLField(blank=True, default="")

    # Status & ordering
    status = models.CharField(
        max_length=20,
        choices=PractitionerStatus.choices,
        default=PractitionerStatus.ACTIVE,
        db_index=True,
    )
    display_order = models.PositiveIntegerField(default=0)

    # Timestamps / soft-delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "practitioners"
        verbose_name = "Practitioner"
        verbose_name_plural = "Practitioners"
        ordering = ["display_order", "name_en"]
        indexes = [
            models.Index(fields=["clinic", "status", "deleted_at"]),
        ]

    def __str__(self):
        return f"{self.name_en} ({self.clinic.name_en})"
