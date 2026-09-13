"""
Integration tests for the Referral Registration & Milestone Engine.
Verifies spec §1 (Rule 10), §5.1, §5.4, §7 (Rule 5).
"""
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import PatientProfile, User, UserRole
from apps.accounts.services.otp import OtpService
from apps.referrals.models import (
    LedgerTransactionType,
    ReferralInvite,
    ReferralInviteStatus,
    ReferralPointsLedger,
)

REGISTER_URL = "/api/v1/auth/register/"
VERIFY_OTP_URL = "/api/v1/auth/verify-otp/"


@pytest.mark.django_db
class TestReferralRegistrationIntegration:
    def setup_method(self):
        self.client = APIClient()

        # Create Referrer (Patient A)
        self.referrer = User.objects.create_user(
            phone="+971501111111",
            full_name="Patient A (Referrer)",
            password="SecurePassword123!",
            role=UserRole.PATIENT,
            is_verified=True,
        )
        self.referrer_profile = self.referrer.patient_profile
        self.referral_code = self.referrer_profile.referral_code

    def test_referral_flow_requires_otp_verification(self):
        """
        Registering with a referral code must NOT award points or increment invites
        until OTP verification succeeds.
        """
        invitee_phone = "+971502222222"

        # 1. Register Invitee (Patient B)
        reg_resp = self.client.post(
            REGISTER_URL,
            {
                "full_name": "Patient B (Invitee)",
                "phone": invitee_phone,
                "password": "SecurePassword123!",
                "referral_code": self.referral_code,
            },
            format="json",
        )
        assert reg_resp.status_code == status.HTTP_201_CREATED

        # Invitee created in DB
        invitee = User.objects.get(phone=invitee_phone)
        assert invitee.is_verified is False
        assert invitee.patient_profile.referred_by_code == self.referral_code

        # Referrer state must remain untouched before OTP verification
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.total_successful_invites == 0
        assert self.referrer_profile.current_points == 0
        assert ReferralInvite.objects.filter(referrer=self.referrer).count() == 0

        # 2. Plant and verify OTP
        otp_code = "123456"
        from apps.accounts.tests.test_auth import _plant_otp
        _plant_otp(invitee_phone, "registration", code=otp_code)

        verify_resp = self.client.post(
            VERIFY_OTP_URL,
            {
                "phone": invitee_phone,
                "otp_code": otp_code,
                "purpose": "registration",
            },
            format="json",
        )
        assert verify_resp.status_code == status.HTTP_200_OK

        # 3. Verify that ReferralInvite is created and marked successful
        invite = ReferralInvite.objects.get(referrer=self.referrer, invitee_phone=invitee_phone)
        assert invite.status == ReferralInviteStatus.SUCCESSFUL

        # 4. Verify referrer total_successful_invites is incremented
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.total_successful_invites == 1

    def test_referral_processing_is_idempotent(self):
        """
        Repeated calls to OTP verify or processing logic must NOT increment
        total_successful_invites twice or award duplicate points.
        """
        invitee_phone = "+971503333333"

        self.client.post(
            REGISTER_URL,
            {
                "full_name": "Patient C",
                "phone": invitee_phone,
                "password": "SecurePassword123!",
                "referral_code": self.referral_code,
            },
            format="json",
        )

        invitee = User.objects.get(phone=invitee_phone)
        from apps.accounts.views import _process_referral_invite

        # Process first time
        _process_referral_invite(invitee)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.total_successful_invites == 1

        # Process second time (simulate re-verification)
        _process_referral_invite(invitee)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.total_successful_invites == 1
        assert ReferralInvite.objects.filter(referrer=self.referrer, invitee_phone=invitee_phone).count() == 1

    def test_milestone_points_awarded_at_thresholds(self):
        """
        Invites milestone awards:
        20 invites -> +100
        35 invites -> +175
        50 invites -> +250
        Total at 50 = 525 points.
        """
        from apps.referrals.services import award_referral_milestones

        self.referrer_profile.total_successful_invites = 19
        self.referrer_profile.save()
        award_referral_milestones(self.referrer)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.current_points == 0

        # Reach 20
        self.referrer_profile.total_successful_invites = 20
        self.referrer_profile.save()
        award_referral_milestones(self.referrer)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.current_points == 100
        assert self.referrer_profile.milestone_20_awarded is True
        assert ReferralPointsLedger.objects.filter(
            patient=self.referrer, transaction_type=LedgerTransactionType.MILESTONE_20
        ).count() == 1

        # Reach 35
        self.referrer_profile.total_successful_invites = 35
        self.referrer_profile.save()
        award_referral_milestones(self.referrer)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.current_points == 275  # 100 + 175
        assert self.referrer_profile.milestone_35_awarded is True

        # Reach 50
        self.referrer_profile.total_successful_invites = 50
        self.referrer_profile.save()
        award_referral_milestones(self.referrer)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.current_points == 525  # 100 + 175 + 250
        assert self.referrer_profile.milestone_50_awarded is True

        # Re-run: strict idempotency check
        award_referral_milestones(self.referrer)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.current_points == 525
        assert ReferralPointsLedger.objects.filter(patient=self.referrer).count() == 3

    def test_self_referral_is_rejected(self):
        """A user cannot refer themselves."""
        from apps.accounts.views import _process_referral_invite

        self.referrer_profile.referred_by_code = self.referrer_profile.referral_code
        self.referrer_profile.save()

        _process_referral_invite(self.referrer)
        self.referrer_profile.refresh_from_db()
        assert self.referrer_profile.total_successful_invites == 0
        assert ReferralInvite.objects.filter(referrer=self.referrer).count() == 0
