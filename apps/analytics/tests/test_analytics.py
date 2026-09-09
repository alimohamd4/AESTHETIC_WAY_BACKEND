from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model

from apps.accounts.models import UserRole, ClinicUser
from apps.clinics.models import Clinic, ClinicStatus
from apps.leads.models import Lead
from apps.analytics.models import AnalyticsEvent, EventType

User = get_user_model()

class AnalyticsTests(APITestCase):
    def setUp(self):
        self.patient = User.objects.create_user(phone="+971500000001", full_name="Patient", role=UserRole.PATIENT)
        self.staff = User.objects.create_user(phone="+971500000002", full_name="Staff", role=UserRole.CLINIC_STAFF)
        self.admin = User.objects.create_user(phone="+971500000003", full_name="Admin", role=UserRole.SUPER_ADMIN)
        
        self.clinic = Clinic.objects.create(name_en="Analytics Clinic", status=ClinicStatus.ACTIVE)
        ClinicUser.objects.create(user=self.staff, clinic=self.clinic)

        self.ingest_url = reverse("api_v1:analytics:events")
        self.clinic_analytics_url = reverse("api_v1:clinic_analytics:dashboard")
        self.admin_analytics_url = reverse("api_v1:admin:analytics-engagement")

    def test_anonymous_event_ingestion(self):
        response = self.client.post(self.ingest_url, {
            "event_type": "app_open",
            "anonymous_id": "anon-1234"
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        event = AnalyticsEvent.objects.first()
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, EventType.APP_OPEN)
        self.assertIsNone(event.user)
        self.assertEqual(event.anonymous_id, "anon-1234")

    def test_authenticated_event_ingestion(self):
        self.client.force_authenticate(user=self.patient)
        
        response = self.client.post(self.ingest_url, {
            "event_type": "clinic_view",
            "clinic": str(self.clinic.id),
            "object_type": "offer",
            "object_id": "00000000-0000-0000-0000-000000000000"
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        event = AnalyticsEvent.objects.first()
        self.assertIsNotNone(event)
        self.assertEqual(event.user, self.patient)
        self.assertEqual(event.clinic, self.clinic)

    def test_clinic_dashboard_aggregation(self):
        # Create some events
        AnalyticsEvent.objects.create(clinic=self.clinic, event_type=EventType.CLINIC_VIEW)
        AnalyticsEvent.objects.create(clinic=self.clinic, event_type=EventType.CLINIC_VIEW)
        AnalyticsEvent.objects.create(clinic=self.clinic, event_type=EventType.WHATSAPP_TAP)
        
        # Create some leads
        Lead.objects.create(patient=self.patient, clinic=self.clinic, reference_code="#1", status="new")
        Lead.objects.create(patient=self.patient, clinic=self.clinic, reference_code="#2", status="contacted")
        
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.clinic_analytics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile_views"], 2)
        self.assertEqual(response.data["whatsapp_taps"], 1)
        self.assertEqual(response.data["total_leads"], 2)
        # 1 out of 2 leads contacted = 50%
        self.assertEqual(response.data["contacted_conversion_percentage"], 50.0)

    def test_admin_engagement_analytics(self):
        AnalyticsEvent.objects.create(event_type=EventType.APP_OPEN)
        AnalyticsEvent.objects.create(event_type=EventType.APP_OPEN)
        
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.admin_analytics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["app_opens_30d"], 2)
