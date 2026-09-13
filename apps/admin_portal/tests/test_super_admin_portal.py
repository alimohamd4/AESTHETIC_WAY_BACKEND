"""
Comprehensive Phase 16 Super Admin Portal Tests
Covers all 47 test requirements from the specification.
"""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.admin_portal.models import AdminActionType, AdminAuditLog
from apps.analytics.models import AnalyticsEvent, EventType
from apps.app_config.models import PlatformSetting
from apps.articles.models import Article
from apps.articles.models import ContentStatus as ArticleStatus
from apps.clinics.models import Clinic, ClinicBranch, ClinicStatus, SubscriptionTier
from apps.leads.models import Lead, LeadStatus, LeadType
from apps.offers.models import Offer, OfferStatus
from apps.practitioners.models import Practitioner, PractitionerType
from apps.products.models import ContentStatus as ProductStatus
from apps.products.models import Product
from apps.treatments.models import Category, Treatment

User = get_user_model()


class SuperAdminPortalTests(APITestCase):
    def setUp(self):
        # Users
        self.super_admin = User.objects.create_user(
            phone="+971501111111",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_verified=True,
        )
        self.clinic_admin = User.objects.create_user(
            phone="+971502222222",
            full_name="Clinic Admin",
            role=UserRole.CLINIC_ADMIN,
            is_verified=True,
        )
        self.clinic_staff = User.objects.create_user(
            phone="+971503333333",
            full_name="Clinic Staff",
            role=UserRole.CLINIC_STAFF,
            is_verified=True,
        )
        self.patient = User.objects.create_user(
            phone="+971504444444",
            full_name="Patient User",
            role=UserRole.PATIENT,
            is_verified=True,
        )

        # Clinic
        self.clinic = Clinic.objects.create(
            name_en="Prime Aesthetics Dubai",
            name_ar="برايم استاتيكس دبي",
            slug="prime-aesthetics-dubai",
            city="Dubai",
            emirate="Dubai",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.BASIC,
            license_number="DHA-CL-99881",
            phone="+97143999999",
            whatsapp="+971509999999",
        )
        self.branch = ClinicBranch.objects.create(
            clinic=self.clinic,
            name_en="Jumeirah Branch",
            city="Dubai",
            phone="+97143999999",
            is_main_branch=True,
        )

        # Catalog
        self.category = Category.objects.create(name_en="Dermatology", slug="dermatology")
        self.practitioner = Practitioner.objects.create(
            clinic=self.clinic,
            name_en="Dr. Maya Lin",
            type=PractitionerType.DOCTOR,
        )
        self.treatment = Treatment.objects.create(
            clinic=self.clinic,
            category=self.category,
            name_en="HydraFacial Glow",
            price=Decimal("650.00"),
        )
        self.offer = Offer.objects.create(
            clinic=self.clinic,
            title_en="Summer Glow Offer",
            original_price=Decimal("650.00"),
            offer_price=Decimal("450.00"),
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=30),
            status=OfferStatus.PENDING,
        )
        self.product = Product.objects.create(
            clinic=self.clinic,
            name_en="Rejuvenating Sunscreen SPF50",
            price=Decimal("180.00"),
            status=ProductStatus.PENDING,
        )
        self.article = Article.objects.create(
            clinic=self.clinic,
            title_en="Guide to Post-Laser Care",
            slug="guide-to-post-laser-care",
            status=ArticleStatus.PENDING,
        )

        # Lead
        self.lead = Lead.objects.create(
            clinic=self.clinic,
            branch=self.branch,
            practitioner=self.practitioner,
            treatment=self.treatment,
            patient=self.patient,
            patient_name="Fatima Al Hashimi",
            patient_phone="+971501234567",
            status=LeadStatus.NEW,
            lead_type=LeadType.CONSULTATION,
            consent_accepted=True,
        )

        # Analytics
        self.event = AnalyticsEvent.objects.create(
            event_type=EventType.CLINIC_VIEW,
            clinic=self.clinic,
            user=self.patient,
        )

        # URLs
        self.dashboard_url = reverse("api_v1:admin:dashboard")
        self.clinics_url = reverse("api_v1:admin:clinic-list")
        self.clinic_detail_url = reverse("api_v1:admin:clinic-detail", kwargs={"pk": self.clinic.id})
        self.clinic_suspend_url = reverse("api_v1:admin:clinic-suspend", kwargs={"pk": self.clinic.id})
        self.clinic_activate_url = reverse("api_v1:admin:clinic-activate", kwargs={"pk": self.clinic.id})
        self.clinic_verify_url = reverse("api_v1:admin:clinic-verify", kwargs={"pk": self.clinic.id})
        self.clinic_audit_url = reverse("api_v1:admin:clinic-audit", kwargs={"pk": self.clinic.id})
        self.leads_url = reverse("api_v1:admin:leads")
        self.lead_detail_url = reverse("api_v1:admin:lead-detail", kwargs={"pk": self.lead.id})
        self.moderation_url = reverse("api_v1:admin:moderation-queue")
        self.offer_approve_url = reverse("api_v1:admin:offer-approve", kwargs={"pk": self.offer.id})
        self.offer_reject_url = reverse("api_v1:admin:offer-reject", kwargs={"pk": self.offer.id})
        self.product_suspend_url = reverse("api_v1:admin:product-suspend", kwargs={"pk": self.product.id})
        self.article_approve_url = reverse("api_v1:admin:article-approve", kwargs={"pk": self.article.id})
        self.analytics_url = reverse("api_v1:admin:analytics")
        self.settings_url = reverse("api_v1:admin:settings")
        self.audit_url = reverse("api_v1:admin:audit")

    # =================================================================
    # 1–4. Permission Boundaries
    # =================================================================
    def test_01_anonymous_user_cannot_access_admin_apis(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_02_patient_cannot_access_admin_apis(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_03_clinic_staff_cannot_access_admin_apis(self):
        self.client.force_authenticate(user=self.clinic_staff)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_04_clinic_admin_cannot_access_admin_apis(self):
        self.client.force_authenticate(user=self.clinic_admin)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # =================================================================
    # 5–6. Dashboard
    # =================================================================
    def test_05_super_admin_can_access_dashboard(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_06_dashboard_aggregates_are_correct(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["total_clinics"], 1)
        self.assertEqual(data["active_clinics"], 1)
        self.assertEqual(data["suspended_clinics"], 0)
        self.assertEqual(data["total_patients"], 1)
        self.assertEqual(data["total_practitioners"], 1)
        self.assertEqual(data["total_treatments"], 1)
        self.assertEqual(data["total_offers"], 1)
        self.assertEqual(data["total_products"], 1)
        self.assertEqual(data["total_articles"], 1)
        self.assertEqual(data["total_leads"], 1)
        self.assertEqual(data["leads_by_status"]["new"], 1)
        self.assertEqual(data["active_subscription_tiers"]["basic"], 1)

    # =================================================================
    # 7–10. Clinic Administration & Details
    # =================================================================
    def test_07_clinic_listing_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.clinics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        item = response.data["results"][0]
        self.assertEqual(item["name_en"], "Prime Aesthetics Dubai")
        self.assertIn("branches_count", item)
        self.assertIn("practitioners_count", item)

    def test_08_clinic_search_works(self):
        self.client.force_authenticate(user=self.super_admin)
        # Match
        res1 = self.client.get(self.clinics_url, {"search": "Prime"})
        self.assertEqual(len(res1.data["results"]), 1)
        # Non-match
        res2 = self.client.get(self.clinics_url, {"search": "NonExistentClinic"})
        self.assertEqual(len(res2.data["results"]), 0)

    def test_09_clinic_status_filtering_works(self):
        self.client.force_authenticate(user=self.super_admin)
        res_active = self.client.get(self.clinics_url, {"status": "active"})
        self.assertEqual(len(res_active.data["results"]), 1)
        res_suspended = self.client.get(self.clinics_url, {"status": "suspended"})
        self.assertEqual(len(res_suspended.data["results"]), 0)

    def test_10_clinic_detail_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.clinic_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data["id"], str(self.clinic.id))
        self.assertEqual(data["license_number"], "DHA-CL-99881")
        self.assertEqual(data["subscription_tier"], "basic")
        self.assertIn("branches", data)
        self.assertEqual(len(data["branches"]), 1)
        self.assertEqual(data["practitioners_count"], 1)
        self.assertEqual(data["treatments_count"], 1)
        self.assertEqual(data["leads_count"], 1)

    # =================================================================
    # 11–15. Clinic Status Management: Suspend / Activate / Verify
    # =================================================================
    def test_11_clinic_suspension_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(self.clinic_suspend_url, {
            "reason": "Non-compliance with regulatory requirements"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.status, ClinicStatus.SUSPENDED)
        self.assertEqual(self.clinic.moderation_notes, "Non-compliance with regulatory requirements")
        self.assertEqual(self.clinic.moderated_by, self.super_admin)

    def test_12_suspended_clinic_disappears_from_public_discovery(self):
        # First verify it appears when active
        pub_url = reverse("api_v1:clinics:clinic-list")
        res_active = self.client.get(pub_url)
        self.assertEqual(res_active.status_code, status.HTTP_200_OK)
        clinic_ids = [c["id"] for c in res_active.data.get("results", [])]
        self.assertIn(str(self.clinic.id), clinic_ids)

        # Suspend the clinic
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(self.clinic_suspend_url, {"reason": "Suspended for test"})

        # Verify it disappears from public discovery
        self.client.force_authenticate(user=None)
        res_pub = self.client.get(pub_url)
        self.assertEqual(res_pub.status_code, status.HTTP_200_OK)
        clinic_ids_after = [c["id"] for c in res_pub.data.get("results", [])]
        self.assertNotIn(str(self.clinic.id), clinic_ids_after)

    def test_13_suspended_clinic_cannot_receive_new_leads(self):
        # Suspend clinic
        self.clinic.status = ClinicStatus.SUSPENDED
        self.clinic.save()

        # Attempt to create lead as patient
        self.client.force_authenticate(user=self.patient)
        lead_submit_url = reverse("api_v1:leads:create")
        payload = {
            "clinic": str(self.clinic.id),
            "treatment": str(self.treatment.id),
            "patient_name": "Test Patient",
            "patient_phone": "+971509998877",
            "consent_accepted": True,
        }
        response = self.client.post(lead_submit_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_14_clinic_activation_works(self):
        self.clinic.status = ClinicStatus.SUSPENDED
        self.clinic.save()

        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(self.clinic_activate_url, {"reason": "Resolved issues"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.status, ClinicStatus.ACTIVE)

    def test_15_clinic_verification_works(self):
        self.clinic.status = ClinicStatus.PENDING
        self.clinic.save()

        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(self.clinic_verify_url, {"reason": "Trade license verified"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.status, ClinicStatus.ACTIVE)
        self.assertTrue(response.data.get("is_verified"))

    # =================================================================
    # 16–19. Tier Management & Security Boundaries
    # =================================================================
    def test_16_tier_change_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.patch(self.clinic_detail_url, {
            "subscription_tier": "vip"
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.subscription_tier, SubscriptionTier.VIP)

    def test_17_clinic_user_cannot_change_tier(self):
        self.client.force_authenticate(user=self.clinic_admin)
        response = self.client.patch(self.clinic_detail_url, {
            "subscription_tier": "vip",
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.subscription_tier, SubscriptionTier.BASIC)

    def test_18_clinic_user_cannot_suspend_another_clinic(self):
        self.client.force_authenticate(user=self.clinic_admin)
        response = self.client.post(self.clinic_suspend_url, {"reason": "Malicious attempt"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.clinic.refresh_from_db()
        self.assertEqual(self.clinic.status, ClinicStatus.ACTIVE)

    def test_19_unauthorized_role_manipulation_is_rejected(self):
        self.client.force_authenticate(user=self.patient)
        # Attempt to call super admin endpoints
        response = self.client.post(self.clinic_activate_url, {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # =================================================================
    # 20–23. Admin Lead Supervision & PII Scrubbing
    # =================================================================
    def test_20_admin_lead_listing_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.leads_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 1)
        item = response.data["results"][0]
        self.assertEqual(item["reference_code"], self.lead.reference_code)
        self.assertEqual(item["patient_name"], "Fatima Al Hashimi")

    def test_21_admin_lead_detail_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.lead_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["reference_code"], self.lead.reference_code)

    def test_22_lead_filters_work(self):
        self.client.force_authenticate(user=self.super_admin)
        # Filter by status
        res_new = self.client.get(self.leads_url, {"status": "new"})
        self.assertEqual(len(res_new.data["results"]), 1)
        res_closed = self.client.get(self.leads_url, {"status": "closed"})
        self.assertEqual(len(res_closed.data["results"]), 0)
        # Filter by clinic
        res_clinic = self.client.get(self.leads_url, {"clinic": str(self.clinic.id)})
        self.assertEqual(len(res_clinic.data["results"]), 1)
        # Filter by reference_code
        res_ref = self.client.get(self.leads_url, {"reference_code": self.lead.reference_code})
        self.assertEqual(len(res_ref.data["results"]), 1)

    def test_23_patient_sensitive_fields_are_scrubbed_appropriately(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.lead_detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Confirm no passwords, tokens, or OTPs exist in response
        self.assertNotIn("password", response.data)
        self.assertNotIn("token", response.data)
        self.assertNotIn("otp", response.data)

    # =================================================================
    # 24–29. Content Moderation
    # =================================================================
    def test_24_moderation_listing_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.moderation_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 3)

    def test_25_offer_approval_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(self.offer_approve_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, OfferStatus.ACTIVE)
        self.assertTrue(self.offer.is_active)

    def test_26_offer_rejection_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(self.offer_reject_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.status, OfferStatus.REJECTED)
        self.assertFalse(self.offer.is_active)

    def test_27_product_moderation_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(self.product_suspend_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, ProductStatus.SUSPENDED)
        self.assertFalse(self.product.is_active)

    def test_28_article_moderation_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(self.article_approve_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.article.refresh_from_db()
        self.assertEqual(self.article.status, ArticleStatus.ACTIVE)

    def test_29_invalid_moderation_transition_is_rejected(self):
        self.client.force_authenticate(user=self.super_admin)
        offer_mod_url = reverse("api_v1:admin:offer-moderate", kwargs={"pk": self.offer.id})
        response = self.client.post(offer_mod_url, {
            "status": "invalid_status_xyz"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =================================================================
    # 30–36. Audit Logging & Immutability
    # =================================================================
    def test_30_moderation_actions_are_audited(self):
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(self.offer_approve_url)
        log = AdminAuditLog.objects.filter(
            action_type=AdminActionType.MODERATE_CONTENT,
            entity_id=self.offer.id,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.admin, self.super_admin)

    def test_31_tier_changes_are_audited(self):
        self.client.force_authenticate(user=self.super_admin)
        self.client.patch(self.clinic_detail_url, {"subscription_tier": "featured"})
        log = AdminAuditLog.objects.filter(
            action_type=AdminActionType.UPDATE_SUBSCRIPTION,
            entity_id=self.clinic.id,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details["new_tier"], "featured")

    def test_32_clinic_suspension_is_audited(self):
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(self.clinic_suspend_url, {"reason": "Audited suspend"})
        log = AdminAuditLog.objects.filter(
            action_type=AdminActionType.SUSPEND_CLINIC,
            entity_id=self.clinic.id,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.details["reason"], "Audited suspend")

    def test_33_clinic_activation_is_audited(self):
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(self.clinic_activate_url, {"reason": "Audited activate"})
        log = AdminAuditLog.objects.filter(
            action_type=AdminActionType.ACTIVATE_CLINIC,
            entity_id=self.clinic.id,
        ).first()
        self.assertIsNotNone(log)

    def test_34_verification_is_audited(self):
        self.client.force_authenticate(user=self.super_admin)
        self.client.post(self.clinic_verify_url, {"reason": "Audited verify"})
        log = AdminAuditLog.objects.filter(
            action_type=AdminActionType.VERIFY_CLINIC,
            entity_id=self.clinic.id,
        ).first()
        self.assertIsNotNone(log)

    def test_35_audit_endpoint_is_read_only(self):
        self.client.force_authenticate(user=self.super_admin)
        res_post = self.client.post(self.audit_url, {"action_type": "fake"})
        self.assertEqual(res_post.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        res_put = self.client.put(self.audit_url, {})
        self.assertEqual(res_put.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        res_delete = self.client.delete(self.audit_url)
        self.assertEqual(res_delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_36_audit_filtering_works(self):
        self.client.force_authenticate(user=self.super_admin)
        # Create distinct audit records
        AdminAuditLog.objects.create(
            admin=self.super_admin,
            action_type=AdminActionType.SUSPEND_CLINIC,
            entity_type="Clinic",
            entity_id=self.clinic.id,
        )
        AdminAuditLog.objects.create(
            admin=self.super_admin,
            action_type=AdminActionType.UPDATE_SETTINGS,
            entity_type="PlatformSetting",
        )
        # Filter by action_type
        res = self.client.get(self.audit_url, {"action_type": "suspend_clinic"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for item in res.data["results"]:
            self.assertEqual(item["action_type"], "suspend_clinic")

    # =================================================================
    # 37–38. Platform Analytics Aggregation & Date Filtering
    # =================================================================
    def test_37_analytics_aggregation_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.analytics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertIn("total_events", data)
        self.assertIn("clinic_views", data)
        self.assertIn("conversion_metrics", data)
        self.assertIn("daily_trends", data)
        self.assertIn("clinic_engagement", data)
        self.assertEqual(data["clinic_views"], 1)

    def test_38_analytics_date_filtering_works(self):
        self.client.force_authenticate(user=self.super_admin)
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        res_valid = self.client.get(self.analytics_url, {
            "from": str(yesterday),
            "to": str(today),
        })
        self.assertEqual(res_valid.status_code, status.HTTP_200_OK)

        # Inverted range -> 400
        res_invalid = self.client.get(self.analytics_url, {
            "from": str(today),
            "to": str(yesterday),
        })
        self.assertEqual(res_invalid.status_code, status.HTTP_400_BAD_REQUEST)

    # =================================================================
    # 39–41. Settings Management
    # =================================================================
    def test_39_settings_retrieval_works(self):
        PlatformSetting.objects.create(
            key="support_phone",
            value={"phone": "+971581989252"}
        )
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("settings", response.data)
        self.assertIn("config", response.data)
        self.assertEqual(response.data["config"].get("support_phone"), {"phone": "+971581989252"})

    def test_40_allowed_settings_update_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.patch(
            self.settings_url,
            {"key": "maintenance_mode", "value": {"enabled": False}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        setting = PlatformSetting.objects.get(key="maintenance_mode")
        self.assertFalse(setting.value["enabled"])

    def test_41_forbidden_settings_update_is_rejected(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.patch(self.settings_url, {
            "key": "secret_database_password",
            "value": "hacked"
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # =================================================================
    # 42–46. Security, Anti-IDOR, Soft Delete, Pagination & N+1 Check
    # =================================================================
    def test_42_cross_resource_idor_attempts_fail(self):
        self.client.force_authenticate(user=self.super_admin)
        fake_uuid = uuid.uuid4()
        fake_clinic_url = reverse("api_v1:admin:clinic-detail", kwargs={"pk": fake_uuid})
        response = self.client.get(fake_clinic_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        fake_lead_url = reverse("api_v1:admin:lead-detail", kwargs={"pk": fake_uuid})
        res_lead = self.client.get(fake_lead_url)
        self.assertEqual(res_lead.status_code, status.HTTP_404_NOT_FOUND)

    def test_43_soft_deleted_resources_are_handled_correctly(self):
        deleted_clinic = Clinic.objects.create(
            name_en="Deleted Clinic",
            city="Dubai",
            deleted_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.clinics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        clinic_ids = [c["id"] for c in response.data["results"]]
        self.assertNotIn(str(deleted_clinic.id), clinic_ids)

        # But can be requested when include_deleted=true
        res_inc = self.client.get(self.clinics_url, {"include_deleted": "true"})
        inc_ids = [c["id"] for c in res_inc.data["results"]]
        self.assertIn(str(deleted_clinic.id), inc_ids)

    def test_44_pagination_works(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.clinics_url, {"page": 1, "page_size": 10})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_45_search_filter_combinations_work(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(self.clinics_url, {
            "status": "active",
            "tier": "basic",
            "city": "Dubai",
            "search": "Prime",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_46_no_n_plus_one_regression_in_critical_admin_endpoints(self):
        self.client.force_authenticate(user=self.super_admin)
        # Create additional test clinics
        for i in range(5):
            Clinic.objects.create(
                name_en=f"Batch Clinic {i}",
                city="Dubai",
                status=ClinicStatus.ACTIVE,
            )
        # Listing with pre-annotations should run in exactly 2 queries (1 count, 1 data)
        with self.assertNumQueries(2):
            response = self.client.get(self.clinics_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    # =================================================================
    # 47. Clinic Audit Trail Sub-endpoint
    # =================================================================
    def test_47_clinic_audit_trail_endpoint_works(self):
        self.client.force_authenticate(user=self.super_admin)
        # Suspend to generate audit
        self.client.post(self.clinic_suspend_url, {"reason": "Testing clinic audit trail"})
        response = self.client.get(self.clinic_audit_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["action_type"], "suspend_clinic")
