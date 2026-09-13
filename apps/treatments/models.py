import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Category(models.Model):
    """
    Treatment category for the home feed and discovery.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_en = models.CharField(max_length=200)
    name_ar = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True)
    icon = models.URLField(blank=True, default="")
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "treatments_categories"
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["display_order", "name_en"]

    def __str__(self):
        return self.name_en


class TreatmentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REJECTED = "rejected", "Rejected"


class Treatment(models.Model):
    """
    Medical/aesthetic treatment or procedure offered by a clinic.
    Strictly owned by a clinic.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        related_name="treatments",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="treatments",
    )

    # Bilingual identity
    name_en = models.CharField(max_length=200, db_index=True)
    name_ar = models.CharField(max_length=200, blank=True, default="", db_index=True)
    description_en = models.TextField(blank=True, default="")
    description_ar = models.TextField(blank=True, default="")

    # Pricing & status
    price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=TreatmentStatus.choices,
        default=TreatmentStatus.ACTIVE,
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Practitioners performing this treatment (M2M through PractitionerTreatment)
    practitioners = models.ManyToManyField(
        "practitioners.Practitioner",
        through="PractitionerTreatment",
        related_name="treatments",
        blank=True,
    )

    # Timestamps / soft-delete
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "treatments"
        verbose_name = "Treatment"
        verbose_name_plural = "Treatments"
        ordering = ["name_en"]
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["clinic", "is_active", "deleted_at"]),
            models.Index(fields=["clinic", "status"]),
        ]

    def __str__(self):
        return f"{self.name_en} ({self.clinic.name_en if self.clinic_id else 'No Clinic'})"


class PractitionerTreatment(models.Model):
    """
    M2M relationship linking a Practitioner to a Treatment they perform.
    Enforces clinic isolation: both must belong to the exact same clinic.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    practitioner = models.ForeignKey(
        "practitioners.Practitioner",
        on_delete=models.CASCADE,
        related_name="practitioner_treatments",
    )
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.CASCADE,
        related_name="practitioner_treatments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "practitioner_treatments"
        verbose_name = "Practitioner Treatment"
        verbose_name_plural = "Practitioner Treatments"
        constraints = [
            models.UniqueConstraint(
                fields=["practitioner", "treatment"],
                name="unique_practitioner_treatment",
            )
        ]
        indexes = [
            models.Index(fields=["practitioner", "treatment"]),
        ]

    def __str__(self):
        return f"{self.practitioner.name_en} -> {self.treatment.name_en}"

    def clean(self):
        super().clean()
        if self.practitioner_id and self.treatment_id:
            # Query clinic IDs
            practitioner_clinic_id = self.practitioner.clinic_id
            treatment_clinic_id = self.treatment.clinic_id
            if practitioner_clinic_id != treatment_clinic_id:
                raise ValidationError(
                    "Practitioner and Treatment must belong to the same clinic."
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
