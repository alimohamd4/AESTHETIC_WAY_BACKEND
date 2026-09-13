from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ClinicUser, UserRole
from apps.clinics.models import Clinic
from apps.referrals.models import DiscountCodeStatus, ReferralDiscountCode, ReferralPointsLedger
from apps.referrals.services import award_referral_milestones

User = get_user_model()

class ReferralTests(APITestCase):
    def setUp(self):
        # Clinics
        self.clinic = Clinic.objects.create(name_en="Clinic A")

        # Users
        self.patient = User.objects.create_user(phone="+971500000001", full_name="Patient 1", role=UserRole.PATIENT)
        self.profile = self.patient.patient_profile

        self.staff = User.objects.create_user(phone="+971500000002", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff, clinic=self.clinic)

        # URLs
        self.status_url = reverse("api_v1:referrals:my-status")
        self.collect_url = reverse("api_v1:referrals:collect-code")
        self.verify_url = reverse("api_v1:clinic_referrals:verify")
        self.redeem_url = reverse("api_v1:clinic_referrals:redeem")

    def test_milestone_awards(self):
        # Test 20 invites
        self.profile.total_successful_invites = 20
        self.profile.save()
        award_referral_milestones(self.patient)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_points, 100)
        self.assertEqual(ReferralPointsLedger.objects.count(), 1)

        # Test idempotency (should not award again)
        award_referral_milestones(self.patient)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_points, 100)
        self.assertEqual(ReferralPointsLedger.objects.count(), 1)

        # Test 35 invites (+175)
        self.profile.total_successful_invites = 35
        self.profile.save()
        award_referral_milestones(self.patient)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_points, 275) # 100 + 175
        self.assertEqual(ReferralPointsLedger.objects.count(), 2)

        # Test 50 invites (+250)
        self.profile.total_successful_invites = 50
        self.profile.save()
        award_referral_milestones(self.patient)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_points, 525) # 100 + 175 + 250
        self.assertEqual(ReferralPointsLedger.objects.count(), 3)

        # Test no further awards at 60
        self.profile.total_successful_invites = 60
        self.profile.save()
        award_referral_milestones(self.patient)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_points, 525)
        self.assertEqual(ReferralPointsLedger.objects.count(), 3)

    def test_collect_code_insufficient_points(self):
        self.profile.current_points = 499
        self.profile.save()

        # We need to manually add ledger entries since Collect checks ledger directly
        ReferralPointsLedger.objects.create(patient=self.patient, transaction_type="admin_adjustment", points=499)

        self.client.force_authenticate(user=self.patient)
        response = self.client.post(self.collect_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReferralDiscountCode.objects.count(), 0)

    def test_collect_code_success(self):
        ReferralPointsLedger.objects.create(patient=self.patient, transaction_type="admin_adjustment", points=500)

        self.client.force_authenticate(user=self.patient)
        response = self.client.post(self.collect_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("AW-15-", response.data["code"])

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_points, 0)
        self.assertEqual(ReferralDiscountCode.objects.count(), 1)
        self.assertEqual(ReferralPointsLedger.objects.count(), 2)

    @patch("apps.referrals.models.generate_discount_code")
    def test_code_uniqueness(self, mock_generate):
        ReferralDiscountCode.objects.create(patient=self.patient, code="AW-15-TEST")

        mock_generate.side_effect = ["AW-15-TEST", "AW-15-GOOD"]
        code2 = ReferralDiscountCode(patient=self.patient)
        code2.code = "AW-15-TEST"  # Simulate collision from the field default
        code2.save()

        self.assertEqual(code2.code, "AW-15-GOOD")

    def test_clinic_verify_code(self):
        code = ReferralDiscountCode.objects.create(patient=self.patient)

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(self.verify_url, {"code": code.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_valid"])
        self.assertEqual(response.data["status"], DiscountCodeStatus.AVAILABLE)

    def test_clinic_verify_expired(self):
        code = ReferralDiscountCode.objects.create(
            patient=self.patient,
            expires_at=timezone.now() - timedelta(days=1)
        )

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(self.verify_url, {"code": code.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_valid"])

    def test_clinic_redeem_code(self):
        code = ReferralDiscountCode.objects.create(patient=self.patient)

        self.client.force_authenticate(user=self.staff)
        response = self.client.post(self.redeem_url, {"code": code.code})

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        code.refresh_from_db()
        self.assertEqual(code.status, DiscountCodeStatus.USED)
        self.assertEqual(code.redeemed_clinic, self.clinic)

    def test_clinic_double_redeem(self):
        code = ReferralDiscountCode.objects.create(patient=self.patient)

        self.client.force_authenticate(user=self.staff)
        self.client.post(self.redeem_url, {"code": code.code})

        response2 = self.client.post(self.redeem_url, {"code": code.code})
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
