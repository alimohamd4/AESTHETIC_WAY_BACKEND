import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ContentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REJECTED = "rejected", "Rejected"


class Product(models.Model):
    """
    Clinic product available for patient inquiry only (no direct e-commerce).
    Strictly owned by a clinic. Patients cannot own or sell products.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        null=True,
        related_name="products",
    )
    name_en = models.CharField(max_length=200, db_index=True)
    name_ar = models.CharField(max_length=200, blank=True, default="", db_index=True)
    description_en = models.TextField(blank=True, default="")
    description_ar = models.TextField(blank=True, default="")

    # Media integration with existing MediaAsset architecture
    image = models.URLField(blank=True, default="")
    media_asset = models.ForeignKey(
        "media.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )

    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=ContentStatus.choices,
        default=ContentStatus.ACTIVE,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "products"
        verbose_name = "Product"
        verbose_name_plural = "Products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["clinic", "is_active", "deleted_at"]),
        ]

    def __str__(self):
        return f"{self.name_en} ({self.clinic.name_en if self.clinic_id else 'No Clinic'})"

    def clean(self):
        super().clean()
        if not self.clinic_id:
            raise ValidationError("Product must belong to a clinic.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def image_url(self) -> str:
        if self.image:
            return self.image
        if self.media_asset:
            return self.media_asset.url
        return ""
