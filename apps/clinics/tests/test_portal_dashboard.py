import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.analytics.models import AnalyticsEvent, EventType
from apps.articles.models import Article, ContentStatus
from apps.clinics.models import Clinic, ClinicStatus
from apps.leads.models import Lead, LeadStatus
from apps.offers.models import Offer, OfferStatus
from apps.practitioners.models import Practitioner, PractitionerStatus, PractitionerType
from apps.products.models import Product
from apps.referrals.models import DiscountCodeStatus, ReferralDiscountCode
from apps.treatments.models import Category, Treatment, TreatmentStatus

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalDashboard:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.url = reverse("api_v1:clinic_portal_dashboard:dashboard")

        # Clinics
        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", status=ClinicStatus.ACTIVE)
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", status=ClinicStatus.ACTIVE)
        self.clinic_suspended = Clinic.objects.create(name_en="Clinic Suspended", status=ClinicStatus.SUSPENDED)

        # Users
        self.patient = User.objects.create_user(phone="+971501111111", full_name="Patient User", role=UserRole.PATIENT)

        self.staff_a = User.objects.create_user(phone="+971502222222", full_name="Staff Alpha", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_b = User.objects.create_user(phone="+971503333333", full_name="Staff Beta", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_unassigned = User.objects.create_user(phone="+971504444444", full_name="Staff Unassigned", role=UserRole.CLINIC_STAFF)

        self.staff_suspended = User.objects.create_user(phone="+971505555555", full_name="Staff Suspended", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_suspended, clinic=self.clinic_suspended, role_in_clinic=ClinicRoleInClinic.STAFF)

        # Telemetry events for Clinic A
        AnalyticsEvent.objects.create(clinic=self.clinic_a, event_type=EventType.WHATSAPP_TAP)
        AnalyticsEvent.objects.create(clinic=self.clinic_a, event_type=EventType.WHATSAPP_TAP)
        AnalyticsEvent.objects.create(clinic=self.clinic_a, event_type=EventType.CALL_TAP)
        AnalyticsEvent.objects.create(clinic=self.clinic_a, event_type=EventType.MAPS_TAP)
        AnalyticsEvent.objects.create(clinic=self.clinic_a, event_type=EventType.CLINIC_VIEW)

        # Telemetry event for Clinic B (isolation check)
        AnalyticsEvent.objects.create(clinic=self.clinic_b, event_type=EventType.WHATSAPP_TAP)

        # Leads for Clinic A
        Lead.objects.create(clinic=self.clinic_a, patient_name="Lead 1", consent_accepted=True, status=LeadStatus.NEW)
        Lead.objects.create(clinic=self.clinic_a, patient_name="Lead 2", consent_accepted=True, status=LeadStatus.CONTACTED)
        Lead.objects.create(clinic=self.clinic_a, patient_name="Lead 3", consent_accepted=True, status=LeadStatus.CLOSED)

        # Lead for Clinic B
        Lead.objects.create(clinic=self.clinic_b, patient_name="Lead B", consent_accepted=True, status=LeadStatus.NEW)

        # Referral redeemed codes for Clinic A
        patient_ref = User.objects.create_user(phone="+971509999001", full_name="Ref Patient", role=UserRole.PATIENT)
        ReferralDiscountCode.objects.create(
            patient=patient_ref,
            code="AW-15-DASH1",
            status=DiscountCodeStatus.USED,
            redeemed_clinic=self.clinic_a,
            redeemed_at=timezone.now(),
        )

        # Catalog items for Clinic A
        Practitioner.objects.create(clinic=self.clinic_a, name_en="Dr. A", type=PractitionerType.DOCTOR, status=PractitionerStatus.ACTIVE)
        cat = Category.objects.create(name_en="Cat", is_active=True)
        Treatment.objects.create(clinic=self.clinic_a, category=cat, name_en="Treat A", is_active=True, status=TreatmentStatus.ACTIVE)
        now = timezone.now()
        Offer.objects.create(clinic=self.clinic_a, title_en="Off A", original_price=100, offer_price=80, starts_at=now, ends_at=now + timezone.timedelta(days=1), is_active=True, status=OfferStatus.ACTIVE)
        Product.objects.create(clinic=self.clinic_a, name_en="Prod A", is_active=True, status=ContentStatus.ACTIVE)
        Article.objects.create(clinic=self.clinic_a, title_en="Art A", is_published=True, status=ContentStatus.ACTIVE)

    def test_anonymous_user_rejected(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patient_user_rejected(self):
        self.client.force_authenticate(user=self.patient)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_clinic_user_without_assignment_rejected(self):
        self.client.force_authenticate(user=self.staff_unassigned)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_clinic_user_with_suspended_clinic_rejected(self):
        self.client.force_authenticate(user=self.staff_suspended)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authorized_clinic_user_dashboard_aggregations(self):
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["clinic_id"] == str(self.clinic_a.id)
        assert data["clinic_name"] == "Clinic Alpha"

        # Check interactions for Clinic A
        assert data["interactions"]["whatsapp_taps"] == 2
        assert data["interactions"]["call_taps"] == 1
        assert data["interactions"]["maps_taps"] == 1
        assert data["interactions"]["profile_views"] == 1

        # Check leads: 3 total, 1 new, 1 contacted, 1 closed -> conversion 66.7%
        assert data["leads"]["total"] == 3
        assert data["leads"]["new"] == 1
        assert data["leads"]["contacted"] == 1
        assert data["leads"]["closed"] == 1
        assert data["leads"]["conversion_rate_percentage"] == 66.7

        # Check redeemed codes
        assert data["referrals"]["redeemed_discount_codes_count"] == 1

        # Check catalog counts
        assert data["catalog"]["active_practitioners_count"] == 1
        assert data["catalog"]["active_treatments_count"] == 1
        assert data["catalog"]["active_offers_count"] == 1
        assert data["catalog"]["active_products_count"] == 1
        assert data["catalog"]["published_articles_count"] == 1

        # Appointments is None (lead only platform)
        assert data["appointments"] is None

    def test_dashboard_strict_clinic_isolation(self):
        # Staff B sees Clinic B data only
        self.client.force_authenticate(user=self.staff_b)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["clinic_id"] == str(self.clinic_b.id)
        assert data["interactions"]["whatsapp_taps"] == 1
        assert data["interactions"]["call_taps"] == 0
        assert data["leads"]["total"] == 1
        assert data["leads"]["new"] == 1
        assert data["referrals"]["redeemed_discount_codes_count"] == 0
        assert data["catalog"]["active_practitioners_count"] == 0
