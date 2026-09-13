from django.test import TestCase

from apps.clinics.models import Clinic, ClinicBranch


class ClinicBranchModelTests(TestCase):
    def setUp(self):
        self.clinic = Clinic.objects.create(
            name_en="Aesthetic Oasis",
            city="Dubai",
            google_place_id="ChIJ123456789",
            google_maps_url="https://maps.google.com/?q=Dubai",
        )

    def test_clinic_and_branch_google_maps_fields(self):
        """Clinic and ClinicBranch store optional google_place_id and google_maps_url."""
        self.assertEqual(self.clinic.google_place_id, "ChIJ123456789")
        self.assertEqual(self.clinic.google_maps_url, "https://maps.google.com/?q=Dubai")

        branch = ClinicBranch.objects.create(
            clinic=self.clinic,
            name_en="Jumeirah Branch",
            address_en="Jumeirah 1",
            city="Dubai",
            latitude=25.2048,
            longitude=55.2708,
            google_place_id="ChIJ987654321",
            google_maps_url="https://maps.google.com/?q=Jumeirah",
            is_main_branch=True,
        )

        self.assertEqual(branch.clinic, self.clinic)
        self.assertEqual(branch.google_place_id, "ChIJ987654321")
        self.assertEqual(branch.google_maps_url, "https://maps.google.com/?q=Jumeirah")
        self.assertTrue(branch.is_main_branch)
