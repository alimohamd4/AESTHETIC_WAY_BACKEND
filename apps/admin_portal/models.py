import uuid
from django.db import models
from django.conf import settings

class AdminActionType(models.TextChoices):
    SUSPEND_CLINIC = "suspend_clinic", "Suspend Clinic"
    UPDATE_SUBSCRIPTION = "update_subscription", "Update Subscription"
    MODERATE_CONTENT = "moderate_content", "Moderate Content"
    REDEEM_DISCOUNT = "redeem_discount", "Redeem Discount"
    UPDATE_SETTINGS = "update_settings", "Update Settings"

class AdminAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    action_type = models.CharField(max_length=50, choices=AdminActionType.choices)
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type", "created_at"]),
        ]
