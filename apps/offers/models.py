import uuid
from django.db import models

class Offer(models.Model):
    """
    Clinic offers displayed on the home feed and clinic profile.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        "clinics.Clinic", on_delete=models.CASCADE, related_name="offers"
    )
    title_en = models.CharField(max_length=200)
    title_ar = models.CharField(max_length=200, blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    description_ar = models.TextField(blank=True, default="")
    
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    offer_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20, default="pending", choices=[
            ("pending", "Pending"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("rejected", "Rejected")
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "offers"
        verbose_name = "Offer"
        verbose_name_plural = "Offers"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "is_active", "starts_at", "ends_at"]),
        ]

    def __str__(self):
        return self.title_en
