import uuid

from django.conf import settings
from django.db import models


class NotificationChannel(models.TextChoices):
    PUSH = "push", "Push Notification"
    SMS = "sms", "SMS"
    EMAIL = "email", "Email"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class NotificationType(models.TextChoices):
    NEW_LEAD_CLINIC = "new_lead_clinic", "New Lead → Clinic"
    LEAD_CONFIRMATION_PATIENT = "lead_confirmation_patient", "Lead Confirmation → Patient"
    REFERRAL_MILESTONE = "referral_milestone", "Referral Milestone → Patient"
    DISCOUNT_COLLECTED = "discount_collected", "Discount Collected → Patient"
    DISCOUNT_REDEEMED = "discount_redeemed", "Discount Redeemed → Patient"


class Notification(models.Model):
    """
    Persisted record for every notification attempt.
    Created synchronously (status=pending) before the Celery task fires.
    Business state must never depend on this record being 'sent'.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    channel = models.CharField(
        max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.PUSH
    )
    status = models.CharField(
        max_length=20, choices=NotificationStatus.choices, default=NotificationStatus.PENDING
    )
    payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "status"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.notification_type} → {self.recipient_id} ({self.status})"
