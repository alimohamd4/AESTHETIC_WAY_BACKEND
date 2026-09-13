import random
import uuid

from django.conf import settings
from django.db import models


class LeadStatus(models.TextChoices):
    NEW = "new", "New"
    CONTACTED = "contacted", "Contacted"
    CLOSED = "closed", "Closed"

class LeadType(models.TextChoices):
    CONSULTATION = "consultation", "Consultation"
    OFFER = "offer", "Offer"
    PRODUCT_INQUIRY = "product_inquiry", "Product Inquiry"

class PreferredTimeWindow(models.TextChoices):
    MORNING = "morning", "Morning"
    AFTERNOON = "afternoon", "Afternoon"
    EVENING = "evening", "Evening"

def generate_reference_code():
    return f"#REQ-{random.randint(10000, 99999)}"

class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Optional patient auth (null for guests)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leads"
    )

    # Core relations
    clinic = models.ForeignKey(
        "clinics.Clinic", on_delete=models.CASCADE, related_name="leads"
    )
    branch = models.ForeignKey(
        "clinics.ClinicBranch", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    practitioner = models.ForeignKey(
        "practitioners.Practitioner", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    treatment = models.ForeignKey(
        "treatments.Treatment", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    offer = models.ForeignKey(
        "offers.Offer", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    product = models.ForeignKey(
        "products.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )

    # Lead details
    reference_code = models.CharField(max_length=20, unique=True, default=generate_reference_code)
    lead_type = models.CharField(max_length=30, choices=LeadType.choices, default=LeadType.CONSULTATION)
    service_name = models.CharField(max_length=200, blank=True, default="")

    # Patient details
    patient_name = models.CharField(max_length=200)
    patient_phone = models.CharField(max_length=20)
    patient_email = models.EmailField(blank=True, default="")

    preferred_time_window = models.CharField(
        max_length=20, choices=PreferredTimeWindow.choices, blank=True, default=""
    )
    notes = models.TextField(blank=True, default="")
    consent_accepted = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20, choices=LeadStatus.choices, default=LeadStatus.NEW, db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leads"
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "status"]),
            models.Index(fields=["patient"]),
        ]

    def __str__(self):
        return f"{self.reference_code} - {self.patient_name} -> {self.clinic}"

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = generate_reference_code()
        while Lead.objects.filter(reference_code=self.reference_code).exclude(pk=self.pk).exists():
            self.reference_code = generate_reference_code()
        super().save(*args, **kwargs)

class LeadNote(models.Model):
    """Internal clinic note for a lead."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="internal_notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lead_notes"
        ordering = ["-created_at"]

class LeadStatusHistory(models.Model):
    """Audit log for lead status changes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="status_history")
    status = models.CharField(max_length=20, choices=LeadStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "lead_status_history"
        ordering = ["-created_at"]
