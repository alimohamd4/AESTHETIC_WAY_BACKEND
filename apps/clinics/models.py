"""
Clinics app models - Phase 2.

Entities:
  Clinic       - Main clinic entity with bilingual fields, moderation, geo-coords
  ClinicBranch - Physical branch locations for a clinic

Geographic note:
  latitude/longitude stored as DecimalField for SQLite-compatible dev/test.
  Production Docker will migrate to PostGIS PointField via a separate migration
  once GDAL is installed in the container (see BACKEND_ARCHITECTURE.md).
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class ClinicStatus(models.TextChoices):
    PENDING = "pending", "Pending Review"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REJECTED = "rejected", "Rejected"


class SubscriptionTier(models.TextChoices):
    BASIC = "basic", "Basic"
    FEATURED = "featured", "Featured"
    VIP = "vip", "VIP"


class Clinic(models.Model):
    """
    Core Clinic entity.

    SECURITY:
      - subscription_tier, license_number, license_authority, moderation_*
        are INTERNAL fields. PublicClinicSerializer must never expose them.
      - Patient-facing API filters status='active' AND deleted_at__isnull=True.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Bilingual identity
    name_en = models.CharField(max_length=200, db_index=True)
    name_ar = models.CharField(max_length=200, blank=True, default="", db_index=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description_en = models.TextField(blank=True, default="")
    description_ar = models.TextField(blank=True, default="")

    # Contact
    phone = models.CharField(max_length=20, blank=True, default="")
    whatsapp = models.CharField(max_length=20, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    website = models.URLField(blank=True, default="")

    # Address
    address_en = models.CharField(max_length=500, blank=True, default="")
    address_ar = models.CharField(max_length=500, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    emirate = models.CharField(max_length=100, blank=True, default="")

    # Geography (DecimalField for local dev; PostGIS PointField in production Docker)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )

    # Maps fields
    google_place_id = models.CharField(max_length=255, blank=True, default="")
    google_maps_url = models.URLField(blank=True, default="")

    # Media
    logo = models.URLField(blank=True, default="")
    cover_image = models.URLField(blank=True, default="")

    # Rating
    google_rating = models.DecimalField(
        max_digits=3, decimal_places=2, null=True, blank=True
    )

    # Moderation (INTERNAL - never expose to patients)
    status = models.CharField(
        max_length=20,
        choices=ClinicStatus.choices,
        default=ClinicStatus.PENDING,
        db_index=True,
    )
    moderation_notes = models.TextField(blank=True, default="")
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_clinics",
    )
    moderated_at = models.DateTimeField(null=True, blank=True)

    # Subscription (INTERNAL - never expose to patients)
    subscription_tier = models.CharField(
        max_length=20,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.BASIC,
    )

    # License (INTERNAL - never expose to patients)
    license_number = models.CharField(max_length=100, blank=True, default="")
    license_authority = models.CharField(max_length=200, blank=True, default="")

    # Metadata
    is_featured = models.BooleanField(default=False, db_index=True)
    display_order = models.PositiveIntegerField(default=0, db_index=True)

    # Timestamps / soft-delete
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "clinics"
        verbose_name = "Clinic"
        verbose_name_plural = "Clinics"
        ordering = ["display_order", "-is_featured", "name_en"]
        indexes = [
            models.Index(fields=["status", "deleted_at"]),
            models.Index(fields=["is_featured", "display_order"]),
            models.Index(fields=["emirate", "status"]),
        ]

    def __str__(self):
        return self.name_en

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name_en) or f"clinic-{str(self.id)[:8]}"
            slug = base
            n = 1
            while Clinic.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.status == ClinicStatus.ACTIVE and self.deleted_at is None


class ClinicBranch(models.Model):
    """Physical branch location for a clinic."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        Clinic, on_delete=models.CASCADE, related_name="branches"
    )
    name_en = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True, default="")
    address_en = models.CharField(max_length=500, blank=True, default="")
    address_ar = models.CharField(max_length=500, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    google_place_id = models.CharField(max_length=255, blank=True, default="")
    google_maps_url = models.URLField(blank=True, default="")
    is_main_branch = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "clinic_branches"
        verbose_name = "Clinic Branch"
        verbose_name_plural = "Clinic Branches"
        indexes = [
            models.Index(fields=["clinic", "is_active"]),
        ]

    def __str__(self):
        return f"{self.clinic.name_en} - {self.name_en}"
