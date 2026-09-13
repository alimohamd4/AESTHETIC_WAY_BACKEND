import datetime
import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import ClinicUser, UserRole
from apps.clinics.models import Clinic, ClinicBranch, ClinicStatus
from apps.leads.models import Lead, LeadNote, LeadStatus, LeadStatusHistory
from apps.offers.models import Offer
from apps.practitioners.models import Practitioner, PractitionerType
from apps.products.models import Product
from apps.treatments.models import Category, PractitionerTreatment, Treatment

User = get_user_model()


class PatientFlowTestsBase(APITestCase):
    def setUp(self):
        # Clinics
        self.clinic_a = Clinic.objects.create(
            name_en="Prime Aesthetic Clinic",
            name_ar="عيادة برايم للتجميل",
            status=ClinicStatus.ACTIVE,
            phone="+97141112233",
            whatsapp="+971501112233",
            address_en="Jumeirah 1, Dubai",
            city="Dubai"
        )
        self.clinic_b = Clinic.objects.create(
            name_en="Elite Skin Clinic",
            name_ar="عيادة النخبة للبشرة",
            status=ClinicStatus.ACTIVE,
            city="Abu Dhabi"
        )

        # Branches
        self.branch_a = ClinicBranch.objects.create(
            clinic=self.clinic_a,
            name_en="Jumeirah Branch",
            is_active=True
        )
        self.branch_b = ClinicBranch.objects.create(
            clinic=self.clinic_b,
            name_en="Corniche Branch",
            is_active=True
        )

        # Category
        self.category = Category.objects.create(
            name_en="Facial Aesthetics",
            name_ar="تجميل الوجه",
            slug="facial-aesthetics",
            is_active=True,
            display_order=1
        )

        # Practitioners
        self.practitioner_a = Practitioner.objects.create(
            clinic=self.clinic_a,
            name_en="Dr. Layla Noor",
            type=PractitionerType.DOCTOR
        )
        self.practitioner_b = Practitioner.objects.create(
            clinic=self.clinic_b,
            name_en="Dr. Omar Tariq",
            type=PractitionerType.DOCTOR
        )

        # Treatments
        self.treatment_a = Treatment.objects.create(
            clinic=self.clinic_a,
            category=self.category,
            name_en="HydraFacial Glow",
            name_ar="هايدرافيشل نضارة",
            price=750.00,
            is_active=True
        )
        # Link practitioner_a to treatment_a
        PractitionerTreatment.objects.create(
            practitioner=self.practitioner_a,
            treatment=self.treatment_a
        )

        self.treatment_b = Treatment.objects.create(
            clinic=self.clinic_b,
            category=self.category,
            name_en="Laser Skin Rejuvenation",
            price=1200.00,
            is_active=True
        )

        # Offers
        now = timezone.now()
        self.offer_a = Offer.objects.create(
            clinic=self.clinic_a,
            title_en="Summer Glow Offer",
            original_price=1000.00,
            offer_price=699.00,
            starts_at=now - datetime.timedelta(days=1),
            ends_at=now + datetime.timedelta(days=10),
            is_active=True
        )
        self.offer_b = Offer.objects.create(
            clinic=self.clinic_b,
            title_en="Elite Laser Package",
            original_price=1500.00,
            offer_price=999.00,
            starts_at=now - datetime.timedelta(days=1),
            ends_at=now + datetime.timedelta(days=10),
            is_active=True
        )

        # Product
        self.product_a = Product.objects.create(
            clinic=self.clinic_a,
            name_en="SPF 50 Sunscreen",
            price=150.00,
            is_active=True
        )
        self.product_b = Product.objects.create(
            clinic=self.clinic_b,
            name_en="Night Recovery Cream",
            price=250.00,
            is_active=True
        )

        # Users
        self.patient1 = User.objects.create_user(
            phone="+971501111111",
            full_name="Sara Al Mansoori",
            email="sara@example.com",
            role=UserRole.PATIENT
        )
        self.patient2 = User.objects.create_user(
            phone="+971502222222",
            full_name="Fatima Al Hashimi",
            email="fatima@example.com",
            role=UserRole.PATIENT
        )
        self.staff_a = User.objects.create_user(
            phone="+971503333333",
            full_name="Clinic Staff",
            role=UserRole.CLINIC_STAFF
        )
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a)

        # URLs
        self.create_lead_url = reverse("api_v1:leads:create")
        self.my_leads_url = reverse("api_v1:leads:my")
        self.my_leads_count_url = reverse("api_v1:leads:my-count")


class TestPatientLeadSubmission(PatientFlowTestsBase):
    def test_patient_creates_lead_with_all_entities_success(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "branch": str(self.branch_a.id),
            "practitioner": str(self.practitioner_a.id),
            "treatment": str(self.treatment_a.id),
            "preferred_time_window": "morning",
            "notes": "Please call before 11 AM",
            "consent_accepted": True
        }
        response = self.client.post(self.create_lead_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertIn("lead_reference", response.data)
        self.assertIn("#REQ-", response.data["lead_reference"])

        # Check DB record
        lead = Lead.objects.get(reference_code=response.data["lead_reference"])
        self.assertEqual(lead.patient, self.patient1)
        self.assertEqual(lead.clinic, self.clinic_a)
        self.assertEqual(lead.treatment, self.treatment_a)
        self.assertEqual(lead.service_name, "HydraFacial Glow")
        self.assertEqual(lead.patient_name, "Sara Al Mansoori")
        self.assertEqual(lead.patient_phone, "+971501111111")
        self.assertEqual(lead.status, LeadStatus.NEW)

    def test_anonymous_lead_creation_success(self):
        payload = {
            "clinic": str(self.clinic_a.id),
            "service_name": "Consultation",
            "patient_name": "Guest Patient",
            "patient_phone": "+971509999999",
            "patient_email": "guest@example.com",
            "preferred_time_window": "afternoon",
            "consent_accepted": True
        }
        response = self.client.post(self.create_lead_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        lead = Lead.objects.get(reference_code=response.data["lead_reference"])
        self.assertIsNone(lead.patient)
        self.assertEqual(lead.patient_name, "Guest Patient")

    def test_auto_derivation_from_authenticated_patient(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "treatment": str(self.treatment_a.id),
            "consent_accepted": True
        }
        response = self.client.post(self.create_lead_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        lead = Lead.objects.get(reference_code=response.data["lead_reference"])
        self.assertEqual(lead.patient_name, self.patient1.full_name)
        self.assertEqual(lead.patient_phone, self.patient1.phone)
        self.assertEqual(lead.patient_email, self.patient1.email)

    def test_cannot_inject_other_patient_ownership(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "treatment": str(self.treatment_a.id),
            "consent_accepted": True,
            "patient": str(self.patient2.id),
            "patient_id": str(self.patient2.id)
        }
        response = self.client.post(self.create_lead_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        lead = Lead.objects.get(reference_code=response.data["lead_reference"])
        self.assertEqual(lead.patient, self.patient1)
        self.assertNotEqual(lead.patient, self.patient2)

    def test_missing_consent_rejected(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "treatment": str(self.treatment_a.id),
            "consent_accepted": False
        }
        response = self.client.post(self.create_lead_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_submission_within_24h_rejected(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "treatment": str(self.treatment_a.id),
            "consent_accepted": True
        }
        res1 = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)

        # Immediate repeat
        res2 = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_submission_after_24h_allowed(self):
        self.client.force_authenticate(user=self.patient1)
        # Create an older lead directly
        past_time = timezone.now() - datetime.timedelta(hours=25)
        lead = Lead.objects.create(
            patient=self.patient1,
            clinic=self.clinic_a,
            treatment=self.treatment_a,
            service_name="HydraFacial Glow",
            patient_name=self.patient1.full_name,
            patient_phone=self.patient1.phone,
            consent_accepted=True
        )
        Lead.objects.filter(id=lead.id).update(created_at=past_time)

        payload = {
            "clinic": str(self.clinic_a.id),
            "treatment": str(self.treatment_a.id),
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)


class TestLeadValidationEdgeCases(PatientFlowTestsBase):
    def test_suspended_clinic_rejected(self):
        self.clinic_a.status = ClinicStatus.SUSPENDED
        self.clinic_a.save()

        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "service_name": "Test",
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_deleted_clinic_rejected(self):
        self.clinic_a.deleted_at = timezone.now()
        self.clinic_a.save()

        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "service_name": "Test",
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_clinic_branch_rejected(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "branch": str(self.branch_b.id),  # Belongs to Clinic B!
            "service_name": "Test",
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_clinic_practitioner_rejected(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "practitioner": str(self.practitioner_b.id),  # Belongs to Clinic B!
            "service_name": "Test",
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_clinic_treatment_rejected(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "treatment": str(self.treatment_b.id),  # Belongs to Clinic B!
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_practitioner_not_assigned_to_treatment_rejected(self):
        # Create a second doctor in Clinic A who is NOT linked to treatment_a
        practitioner_unlinked = Practitioner.objects.create(
            clinic=self.clinic_a,
            name_en="Dr. Unlinked",
            type=PractitionerType.DOCTOR
        )
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "treatment": str(self.treatment_a.id),
            "practitioner": str(practitioner_unlinked.id),
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_clinic_offer_rejected(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "offer": str(self.offer_b.id),  # Belongs to Clinic B!
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_offer_rejected(self):
        now = timezone.now()
        expired_offer = Offer.objects.create(
            clinic=self.clinic_a,
            title_en="Expired Offer",
            original_price=500.00,
            offer_price=300.00,
            starts_at=now - datetime.timedelta(days=10),
            ends_at=now - datetime.timedelta(days=1),
            is_active=True
        )
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "offer": str(expired_offer.id),
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_future_offer_rejected(self):
        now = timezone.now()
        future_offer = Offer.objects.create(
            clinic=self.clinic_a,
            title_en="Future Offer",
            original_price=500.00,
            offer_price=300.00,
            starts_at=now + datetime.timedelta(days=5),
            ends_at=now + datetime.timedelta(days=15),
            is_active=True
        )
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "offer": str(future_offer.id),
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cross_clinic_product_rejected(self):
        self.client.force_authenticate(user=self.patient1)
        payload = {
            "clinic": str(self.clinic_a.id),
            "product": str(self.product_b.id),  # Belongs to Clinic B!
            "consent_accepted": True
        }
        res = self.client.post(self.create_lead_url, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class TestPatientMyLeads(PatientFlowTestsBase):
    def setUp(self):
        super().setUp()
        # Create leads for Patient 1
        self.lead1 = Lead.objects.create(
            patient=self.patient1,
            clinic=self.clinic_a,
            treatment=self.treatment_a,
            practitioner=self.practitioner_a,
            service_name="HydraFacial Glow",
            patient_name=self.patient1.full_name,
            patient_phone=self.patient1.phone,
            status=LeadStatus.NEW,
            consent_accepted=True
        )
        self.lead2 = Lead.objects.create(
            patient=self.patient1,
            clinic=self.clinic_a,
            service_name="Follow-up Consultation",
            patient_name=self.patient1.full_name,
            patient_phone=self.patient1.phone,
            status=LeadStatus.CONTACTED,
            consent_accepted=True
        )
        # Create lead for Patient 2
        self.lead_patient2 = Lead.objects.create(
            patient=self.patient2,
            clinic=self.clinic_b,
            service_name="Laser Treatment",
            patient_name=self.patient2.full_name,
            patient_phone=self.patient2.phone,
            status=LeadStatus.NEW,
            consent_accepted=True
        )

    def test_my_leads_list_scoped_to_authenticated_patient(self):
        self.client.force_authenticate(user=self.patient1)
        res = self.client.get(self.my_leads_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)
        results = res.data["results"]
        result_ids = [r["id"] for r in results]
        self.assertIn(str(self.lead1.id), result_ids)
        self.assertIn(str(self.lead2.id), result_ids)
        self.assertNotIn(str(self.lead_patient2.id), result_ids)

    def test_my_leads_status_filtering(self):
        self.client.force_authenticate(user=self.patient1)
        # Filter status=new
        res_new = self.client.get(f"{self.my_leads_url}?status=new")
        self.assertEqual(res_new.status_code, status.HTTP_200_OK)
        self.assertEqual(res_new.data["count"], 1)
        self.assertEqual(res_new.data["results"][0]["id"], str(self.lead1.id))

        # Filter status=contacted
        res_contacted = self.client.get(f"{self.my_leads_url}?status=contacted")
        self.assertEqual(res_contacted.status_code, status.HTTP_200_OK)
        self.assertEqual(res_contacted.data["count"], 1)
        self.assertEqual(res_contacted.data["results"][0]["id"], str(self.lead2.id))

        # Filter status=closed (0 leads)
        res_closed = self.client.get(f"{self.my_leads_url}?status=closed")
        self.assertEqual(res_closed.status_code, status.HTTP_200_OK)
        self.assertEqual(res_closed.data["count"], 0)

    def test_my_leads_count(self):
        self.client.force_authenticate(user=self.patient1)
        res = self.client.get(self.my_leads_count_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 2)

    def test_my_lead_detail_success(self):
        self.client.force_authenticate(user=self.patient1)
        detail_url = reverse("api_v1:leads:my-detail", args=[self.lead1.id])
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], str(self.lead1.id))
        self.assertEqual(res.data["reference_code"], self.lead1.reference_code)

        # Verify clinic contact information is exposed safely
        clinic_summary = res.data["clinic_summary"]
        self.assertEqual(clinic_summary["phone"], "+97141112233")
        self.assertEqual(clinic_summary["whatsapp"], "+971501112233")
        self.assertEqual(clinic_summary["city"], "Dubai")

        # Verify treatment and practitioner summaries
        self.assertEqual(res.data["treatment_summary"]["name_en"], "HydraFacial Glow")
        self.assertEqual(res.data["practitioner_summary"]["name_en"], "Dr. Layla Noor")

    def test_anti_idor_patient_cannot_access_other_patient_lead_detail(self):
        self.client.force_authenticate(user=self.patient1)
        # Patient 1 tries to access Patient 2's lead
        detail_url = reverse("api_v1:leads:my-detail", args=[self.lead_patient2.id])
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_lead_returns_404(self):
        self.client.force_authenticate(user=self.patient1)
        detail_url = reverse("api_v1:leads:my-detail", args=[uuid.uuid4()])
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_internal_fields_never_exposed_in_patient_lead(self):
        # Attach internal note and status history to lead 1
        LeadNote.objects.create(lead=self.lead1, note="Internal VIP patient comment")
        LeadStatusHistory.objects.create(lead=self.lead1, status=LeadStatus.NEW)

        self.client.force_authenticate(user=self.patient1)
        detail_url = reverse("api_v1:leads:my-detail", args=[self.lead1.id])
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertNotIn("internal_notes", res.data)
        self.assertNotIn("status_history", res.data)
        self.assertNotIn("moderation_notes", res.data)


class TestPatientPermissionsAndIntegrations(PatientFlowTestsBase):
    def test_anonymous_user_cannot_access_my_leads(self):
        res = self.client.get(self.my_leads_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_clinic_staff_cannot_access_patient_my_leads(self):
        self.client.force_authenticate(user=self.staff_a)
        res = self.client.get(self.my_leads_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_access_clinic_portal_dashboard(self):
        self.client.force_authenticate(user=self.patient1)
        dashboard_url = reverse("api_v1:clinic_portal_dashboard:dashboard")
        res = self.client.get(dashboard_url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_support_info_endpoint(self):
        support_url = reverse("api_v1:app_config:support-info")
        res = self.client.get(support_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["support_phone"], "+971581989252")
        self.assertEqual(res.data["support_whatsapp"], "+971581989252")
        self.assertEqual(res.data["support_phone_display"], "+971 58 198 9252")

    def test_referral_my_status_spec_fields(self):
        self.client.force_authenticate(user=self.patient1)
        ref_url = reverse("api_v1:referrals:my-status")
        res = self.client.get(ref_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("referral_code", res.data)
        self.assertIn("successful_invites_count", res.data)
        self.assertEqual(res.data["points_to_collect"], 500)
        self.assertIn("can_collect_code", res.data)
        self.assertFalse(res.data["points_expire"])
        self.assertIn("milestones", res.data)

    def test_patient_leads_alias_route(self):
        # Create lead for Patient 1
        lead = Lead.objects.create(
            patient=self.patient1,
            clinic=self.clinic_a,
            service_name="Test Consultation",
            patient_name=self.patient1.full_name,
            patient_phone=self.patient1.phone,
            consent_accepted=True
        )
        self.client.force_authenticate(user=self.patient1)
        list_url = reverse("api_v1:patient_leads:list")
        res_list = self.client.get(list_url)
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(res_list.data["count"], 1)

        detail_url = reverse("api_v1:patient_leads:detail", args=[lead.id])
        res_detail = self.client.get(detail_url)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.data["id"], str(lead.id))

    def test_analytics_event_ingestion(self):
        self.client.force_authenticate(user=self.patient1)
        events_url = reverse("api_v1:analytics:events")
        for event_type in ["whatsapp_tap", "call_tap", "maps_tap"]:
            payload = {
                "event_type": event_type,
                "clinic": str(self.clinic_a.id),
                "metadata": {"source_screen": "clinic_profile"}
            }
            res = self.client.post(events_url, payload, format="json")
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
