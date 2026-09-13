from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.admin_portal.models import AdminActionType, AdminAuditLog
from apps.app_config.models import PlatformSetting
from apps.clinics.models import Clinic, ClinicStatus, SubscriptionTier
from apps.offers.models import Offer

User = get_user_model()

class AdminPortalTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(phone="+971500000001", full_name="Patient", role=UserRole.PATIENT)
        self.staff = User.objects.create_user(phone="+971500000002", full_name="Staff", role=UserRole.CLINIC_STAFF)
        self.admin = User.objects.create_user(phone="+971500000003", full_name="Super Admin", role=UserRole.SUPER_ADMIN)

        self.clinic = Clinic.objects.create(name_en="Admin Clinic", status=ClinicStatus.ACTIVE)
        self.offer = Offer.objects.create(
            clinic=self.clinic,
            title_en="Admin Offer",
            original_price=100.0,
            offer_price=50.0,
            starts_at=timezone.now(),
            ends_at=timezone.now()
        )

        self.dashboard_url = reverse("api_v1:admin:dashboard")
        self.clinic_status_url = reverse("api_v1:admin:clinic-status", kwargs={"pk": self.clinic.pk})
        self.clinic_sub_url = reverse("api_v1:admin:clinic-subscription", kwargs={"pk": self.clinic.pk})
        self.settings_url = reverse("api_v1:admin:settings")
        self.moderate_offer_url = reverse("api_v1:admin:moderate-content", kwargs={"model_name": "offer", "pk": self.offer.pk})

    def test_permission_boundaries(self):
        # Patient
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Staff
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Super Admin
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_clinic_suspension_audit(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(self.clinic_status_url, {
            "status": "suspended",
            "moderation_notes": "Violation of terms"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.status, ClinicStatus.SUSPENDED)
        self.assertEqual(self.clinic.moderation_notes, "Violation of terms")
        self.assertEqual(self.clinic.moderated_by, self.admin)

        # Verify audit log
        log = AdminAuditLog.objects.filter(entity_id=self.clinic.pk).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action_type, AdminActionType.SUSPEND_CLINIC)
        self.assertEqual(log.details["new_status"], "suspended")

    def test_clinic_subscription_update(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(self.clinic_sub_url, {
            "subscription_tier": "vip"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.subscription_tier, SubscriptionTier.VIP)

        # Verify audit log
        log = AdminAuditLog.objects.filter(entity_id=self.clinic.pk).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action_type, AdminActionType.UPDATE_SUBSCRIPTION)
        self.assertEqual(log.details["new_tier"], "vip")

    def test_update_settings(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.put(self.settings_url, {
            "key": "maintenance_mode",
            "value": {"enabled": True}
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        setting = PlatformSetting.objects.get(key="maintenance_mode")
        self.assertEqual(setting.value["enabled"], True)

        log = AdminAuditLog.objects.filter(entity_type="PlatformSetting").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action_type, AdminActionType.UPDATE_SETTINGS)

    def test_content_moderation(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(self.moderate_offer_url, {
            "status": "suspended"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, "suspended")

        log = AdminAuditLog.objects.filter(entity_id=self.offer.pk).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.action_type, AdminActionType.MODERATE_CONTENT)
