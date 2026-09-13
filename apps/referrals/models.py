import random
import string
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class ReferralInviteStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCESSFUL = "successful", "Successful"
    EXPIRED = "expired", "Expired"

class LedgerTransactionType(models.TextChoices):
    MILESTONE_20 = "milestone_20", "Milestone 20"
    MILESTONE_35 = "milestone_35", "Milestone 35"
    MILESTONE_50 = "milestone_50", "Milestone 50"
    COLLECT_CODE = "collect_code", "Collect Code"
    ADMIN_ADJUSTMENT = "admin_adjustment", "Admin Adjustment"

class DiscountCodeStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    USED = "used", "Used"
    EXPIRED = "expired", "Expired"

def generate_discount_code():
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=4))
    return f"AW-15-{suffix}"

def default_expiration():
    return timezone.now() + timedelta(days=90)

class ReferralInvite(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_invites"
    )
    invitee_phone = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20, choices=ReferralInviteStatus.choices, default=ReferralInviteStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referral_invites"
        ordering = ["-created_at"]
        unique_together = [("referrer", "invitee_phone")]

class ReferralPointsLedger(models.Model):
    """
    Immutable ledger of points.
    Source of truth for patient points balance.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral_ledger"
    )
    transaction_type = models.CharField(max_length=30, choices=LedgerTransactionType.choices)
    points = models.IntegerField()
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "referral_points_ledger"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "created_at"]),
        ]

class ReferralDiscountCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="discount_codes"
    )
    code = models.CharField(max_length=20, unique=True, default=generate_discount_code)
    status = models.CharField(
        max_length=20, choices=DiscountCodeStatus.choices, default=DiscountCodeStatus.AVAILABLE
    )
    discount_percent = models.PositiveSmallIntegerField(default=15)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_clinic = models.ForeignKey(
        "clinics.Clinic", on_delete=models.SET_NULL, null=True, blank=True, related_name="redeemed_codes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expiration)

    class Meta:
        db_table = "referral_discount_codes"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_discount_code()
        while ReferralDiscountCode.objects.filter(code=self.code).exclude(pk=self.pk).exists():
            self.code = generate_discount_code()
        super().save(*args, **kwargs)
