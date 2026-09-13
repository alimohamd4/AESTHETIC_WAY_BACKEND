from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.clinics.models import Clinic
from apps.practitioners.models import Practitioner, PractitionerType


class PractitionerModelTests(TestCase):
    def setUp(self):
        self.clinic = Clinic.objects.create(name_en="Prime Health Clinic", city="Dubai")

    def test_default_type_is_doctor(self):
        """Practitioner defaults to doctor type for existing database compatibility."""
        practitioner = Practitioner.objects.create(
            clinic=self.clinic,
            name_en="Dr. Ahmed",
        )
        self.assertEqual(practitioner.type, PractitionerType.DOCTOR)

    def test_valid_practitioner_types(self):
        """Practitioner supports doctor, nurse, and licensed_professional types."""
        p_doc = Practitioner.objects.create(
            clinic=self.clinic, name_en="Dr. Smith", type=PractitionerType.DOCTOR
        )
        p_nurse = Practitioner.objects.create(
            clinic=self.clinic, name_en="Nurse Sarah", type=PractitionerType.NURSE
        )
        p_pro = Practitioner.objects.create(
            clinic=self.clinic, name_en="Therapist Mona", type=PractitionerType.LICENSED_PROFESSIONAL
        )

        self.assertEqual(p_doc.type, "doctor")
        self.assertEqual(p_nurse.type, "nurse")
        self.assertEqual(p_pro.type, "licensed_professional")

    def test_invalid_type_rejected(self):
        """Invalid practitioner type is rejected by full_clean validation."""
        p = Practitioner(
            clinic=self.clinic,
            name_en="Unknown Role",
            type="astrologer",
        )
        with self.assertRaises(ValidationError):
            p.full_clean()
