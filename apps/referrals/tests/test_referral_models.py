from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import UserRole
from apps.referrals.models import DiscountCodeStatus, ReferralDiscountCode

User = get_user_model()


class ReferralModelTests(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            phone="+971501112233",
            full_name="Fatima Ali",
            role=UserRole.PATIENT,
        )

    def test_discount_percent_default(self):
        """ReferralDiscountCode discount_percent defaults to 15%."""
        code = ReferralDiscountCode.objects.create(patient=self.patient)
        self.assertEqual(code.discount_percent, 15)
        self.assertEqual(code.status, DiscountCodeStatus.AVAILABLE)
        self.assertTrue(code.code.startswith("AW-15-"))

    def test_custom_discount_percent(self):
        """ReferralDiscountCode allows setting custom discount_percent."""
        code = ReferralDiscountCode.objects.create(
            patient=self.patient,
            discount_percent=20,
        )
        self.assertEqual(code.discount_percent, 20)
