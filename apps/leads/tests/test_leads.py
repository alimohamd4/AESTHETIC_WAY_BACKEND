from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.accounts.models import UserRole, ClinicUser
from apps.leads.models import Lead, LeadStatus, LeadNote, LeadStatusHistory

User = get_user_model()

class LeadsTests(APITestCase):
    def setUp(self):
        # Clinics
        self.clinic_a = Clinic.objects.create(name_en="Clinic A")
        self.clinic_b = Clinic.objects.create(name_en="Clinic B")

        # Users
        self.patient1 = User.objects.create_user(phone="+971500000001", full_name="Patient 1", role=UserRole.PATIENT)
        self.patient2 = User.objects.create_user(phone="+971500000002", full_name="Patient 2", role=UserRole.PATIENT)
        
        self.staff_a = User.objects.create_user(phone="+971500000003", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a)

        self.staff_b = User.objects.create_user(phone="+971500000004", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b)

        self.admin = User.objects.create_superuser(phone="+971500000005", full_name="Admin", password="pass")

        # URLs
        self.create_url = reverse("api_v1:leads:create")
        self.my_leads_url = reverse("api_v1:leads:my")
        self.clinic_leads_url = reverse("api_v1:clinic_leads:clinic-leads-list")

        # Base Lead Payload
        self.lead_payload = {
            "clinic": str(self.clinic_a.id),
            "lead_type": "consultation",
            "service_name": "Laser",
            "patient_name": "Patient 1",
            "patient_phone": "+971500000001",
            "consent_accepted": True
        }

    def test_patient_creates_lead_success(self):
        self.client.force_authenticate(user=self.patient1)
        response = self.client.post(self.create_url, self.lead_payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Lead.objects.filter(patient=self.patient1).exists())
        self.assertIn("lead_reference", response.data)
        
        # Test My Leads logic
        response2 = self.client.get(self.my_leads_url)
        self.assertEqual(len(response2.data["results"]), 1)
        
        # Verify no internal fields are exposed
        lead_data = response2.data["results"][0]
        self.assertNotIn("internal_notes", lead_data)
        self.assertNotIn("status_history", lead_data)

    def test_consent_validation(self):
        payload = self.lead_payload.copy()
        payload["consent_accepted"] = False
        response = self.client.post(self.create_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("consent_accepted", response.data.get("error", {}).get("fields", {}))

    def test_patient_isolation(self):
        # Patient 1 creates lead
        self.client.force_authenticate(user=self.patient1)
        self.client.post(self.create_url, self.lead_payload)

        # Patient 2 tries to get leads
        self.client.force_authenticate(user=self.patient2)
        response = self.client.get(self.my_leads_url)
        self.assertEqual(len(response.data["results"]), 0)

    def test_clinic_isolation(self):
        # Create lead for clinic A
        Lead.objects.create(clinic=self.clinic_a, patient_name="Test", consent_accepted=True)

        # Staff A sees 1 lead
        self.client.force_authenticate(user=self.staff_a)
        response_a = self.client.get(self.clinic_leads_url)
        self.assertEqual(len(response_a.data["results"]), 1)

        # Staff B sees 0 leads
        self.client.force_authenticate(user=self.staff_b)
        response_b = self.client.get(self.clinic_leads_url)
        self.assertEqual(len(response_b.data["results"]), 0)

    def test_clinic_update_status(self):
        lead = Lead.objects.create(clinic=self.clinic_a, patient_name="Test", consent_accepted=True, status=LeadStatus.NEW)
        
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_leads:clinic-leads-detail", args=[lead.id])
        
        response = self.client.patch(url, {"status": LeadStatus.CONTACTED})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadStatus.CONTACTED)
        
        # Verify history is created
        self.assertEqual(LeadStatusHistory.objects.count(), 1)
        self.assertEqual(LeadStatusHistory.objects.first().status, LeadStatus.CONTACTED)

    def test_super_admin_read_only(self):
        lead = Lead.objects.create(clinic=self.clinic_a, patient_name="Test", consent_accepted=True)
        
        self.client.force_authenticate(user=self.admin)
        
        # Can read
        response_list = self.client.get(self.clinic_leads_url)
        self.assertEqual(len(response_list.data["results"]), 1)
        
        # Cannot patch
        url = reverse("api_v1:clinic_leads:clinic-leads-detail", args=[lead.id])
        response_patch = self.client.patch(url, {"status": LeadStatus.CONTACTED})
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_prevention(self):
        self.client.force_authenticate(user=self.patient1)
        self.client.post(self.create_url, self.lead_payload)
        
        # Immediate duplicate submission
        response2 = self.client.post(self.create_url, self.lead_payload)
        self.assertEqual(response2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @patch("apps.leads.models.random.randint")
    def test_reference_uniqueness(self, mock_randint):
        # Force the first generated code to collide
        mock_randint.side_effect = [12345, 12345, 99999]
        
        Lead.objects.create(clinic=self.clinic_a, patient_name="Test", consent_accepted=True)
        lead2 = Lead.objects.create(clinic=self.clinic_a, patient_name="Test 2", consent_accepted=True)
        
        self.assertEqual(lead2.reference_code, "#REQ-99999")
