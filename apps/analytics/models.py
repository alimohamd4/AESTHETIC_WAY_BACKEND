import uuid
from django.db import models
from django.conf import settings

class EventType(models.TextChoices):
    APP_OPEN = "app_open", "App Open"
    CLINIC_VIEW = "clinic_view", "Clinic View"
    WHATSAPP_TAP = "whatsapp_tap", "WhatsApp Tap"
    CALL_TAP = "call_tap", "Call Tap"
    MAPS_TAP = "maps_tap", "Maps Tap"
    LEAD_SUBMITTED = "lead_submitted", "Lead Submitted"

class AnalyticsEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    anonymous_id = models.CharField(max_length=255, null=True, blank=True)
    
    clinic = models.ForeignKey(
        "clinics.Clinic", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="analytics_events"
    )
    
    object_type = models.CharField(max_length=100, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    
    metadata = models.JSONField(default=dict, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "analytics_events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["clinic", "event_type", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]
