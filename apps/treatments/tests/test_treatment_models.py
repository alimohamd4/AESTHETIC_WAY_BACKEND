from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.practitioners.models import Practitioner, PractitionerType
from apps.treatments.models import (
    Category,
    PractitionerTreatment,
    Treatment,
    TreatmentStatus,
)


class TreatmentModelTests(TestCase):
    def setUp(self):
        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", city="Dubai")
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", city="Abu Dhabi")

        self.category = Category.objects.create(
            name_en="Laser Treatments",
            name_ar="علاجات الليزر",
            slug="laser-treatments",
        )

        self.doc_a = Practitioner.objects.create(
            clinic=self.clinic_a,
            name_en="Dr. Alpha",
            type=PractitionerType.DOCTOR,
        )
        self.doc_b = Practitioner.objects.create(
            clinic=self.clinic_b,
            name_en="Dr. Beta",
            type=PractitionerType.DOCTOR,
        )

    def test_treatment_belongs_to_clinic_and_category(self):
        """Treatment belongs to a specific clinic and category."""
        treatment = Treatment.objects.create(
            clinic=self.clinic_a,
            category=self.category,
            name_en="Full Face Laser",
            name_ar="ليزر الوجه الكامل",
            description_en="Full face gentle laser session",
            price=750.00,
            status=TreatmentStatus.ACTIVE,
            is_active=True,
        )
        self.assertEqual(treatment.clinic, self.clinic_a)
        self.assertEqual(treatment.category, self.category)
        self.assertEqual(float(treatment.price), 750.00)
        self.assertIn(treatment, self.clinic_a.treatments.all())
        self.assertIn(treatment, self.category.treatments.all())

    def test_treatment_active_and_soft_delete(self):
        """Treatment supports active toggle and soft-delete."""
        treatment = Treatment.objects.create(
            clinic=self.clinic_a,
            category=self.category,
            name_en="Carbon Laser",
            is_active=True,
        )
        self.assertTrue(treatment.is_active)
        self.assertIsNone(treatment.deleted_at)

        # Soft delete
        treatment.is_active = False
        treatment.deleted_at = timezone.now()
        treatment.save()

        self.assertFalse(treatment.is_active)
        self.assertIsNotNone(treatment.deleted_at)

    def test_practitioner_treatment_relationship_same_clinic(self):
        """Practitioner and treatment in the same clinic link successfully."""
        treatment = Treatment.objects.create(
            clinic=self.clinic_a,
            category=self.category,
            name_en="HydraFacial Glow",
        )
        pt = PractitionerTreatment.objects.create(
            practitioner=self.doc_a,
            treatment=treatment,
        )
        self.assertEqual(pt.practitioner, self.doc_a)
        self.assertEqual(pt.treatment, treatment)
        self.assertIn(self.doc_a, treatment.practitioners.all())

    def test_cross_clinic_relationship_prevented(self):
        """Practitioner from Clinic B cannot be assigned to Treatment from Clinic A."""
        treatment_a = Treatment.objects.create(
            clinic=self.clinic_a,
            category=self.category,
            name_en="Clinic A Treatment",
        )
        pt_invalid = PractitionerTreatment(
            practitioner=self.doc_b,  # from Clinic B
            treatment=treatment_a,     # from Clinic A
        )
        with self.assertRaises(ValidationError):
            pt_invalid.save()

    def test_duplicate_practitioner_treatment_relationship_prevented(self):
        """Duplicate practitioner-treatment assignment is prevented by unique constraint."""
        treatment = Treatment.objects.create(
            clinic=self.clinic_a,
            category=self.category,
            name_en="Unique Test Treatment",
        )
        PractitionerTreatment.objects.create(
            practitioner=self.doc_a,
            treatment=treatment,
        )
        with self.assertRaises((IntegrityError, ValidationError)):
            PractitionerTreatment.objects.create(
                practitioner=self.doc_a,
                treatment=treatment,
            )
