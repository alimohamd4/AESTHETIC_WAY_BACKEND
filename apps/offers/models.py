import uuid

from django.db import models


class OfferStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REJECTED = "rejected", "Rejected"


class Offer(models.Model):
    """
    Clinic offers displayed on the home feed and clinic profile.
    Validity is clinic-controlled via starts_at / ends_at.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        "clinics.Clinic", on_delete=models.CASCADE, related_name="offers"
    )
    title_en = models.CharField(max_length=200, db_index=True)
    title_ar = models.CharField(max_length=200, blank=True, default="", db_index=True)
    description_en = models.TextField(blank=True, default="")
    description_ar = models.TextField(blank=True, default="")

    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Media integration
    image = models.URLField(blank=True, default="")
    media_asset = models.ForeignKey(
        "media.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offers",
    )

    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)

    is_active = models.BooleanField(default=True, db_index=True)
    status = models.CharField(
        max_length=20,
        default=OfferStatus.ACTIVE,
        choices=OfferStatus.choices,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "offers"
        verbose_name = "Offer"
        verbose_name_plural = "Offers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "is_active", "starts_at", "ends_at"]),
            models.Index(fields=["status", "is_active"]),
        ]

    def __str__(self):
        return f"{self.title_en} ({self.clinic.name_en if self.clinic_id else 'No Clinic'})"

    @property
    def image_url(self) -> str:
        if self.image:
            return self.image
        if self.media_asset:
            return self.media_asset.url
        return ""
