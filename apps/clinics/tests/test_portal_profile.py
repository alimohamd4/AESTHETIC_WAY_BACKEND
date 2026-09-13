import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.clinics.models import Clinic, ClinicStatus, SubscriptionTier

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalProfile:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.url = reverse("api_v1:clinic_portal_profile:profile")

        self.clinic_a = Clinic.objects.create(
            name_en="Original Clinic A",
            name_ar="العيادة أ",
            phone="+971501111111",
            city="Dubai",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.BASIC,
            google_rating=4.5,
            is_featured=False,
            moderation_notes="Initial review",
        )
        self.clinic_b = Clinic.objects.create(
            name_en="Original Clinic B",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.VIP,
        )

        self.admin_a = User.objects.create_user(phone="+971502222222", full_name="Admin A", role=UserRole.CLINIC_ADMIN)
        ClinicUser.objects.create(user=self.admin_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.ADMIN)

        self.staff_b = User.objects.create_user(phone="+971503333333", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.patient = User.objects.create_user(phone="+971504444444", full_name="Patient", role=UserRole.PATIENT)

    def test_anonymous_rejected(self):
        assert self.client.get(self.url).status_code == status.HTTP_401_UNAUTHORIZED
        assert self.client.put(self.url, {}).status_code == status.HTTP_401_UNAUTHORIZED

    def test_patient_rejected(self):
        self.client.force_authenticate(user=self.patient)
        assert self.client.get(self.url).status_code == status.HTTP_403_FORBIDDEN
        assert self.client.put(self.url, {}).status_code == status.HTTP_403_FORBIDDEN

    def test_get_profile_returns_own_clinic(self):
        self.client.force_authenticate(user=self.admin_a)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(self.clinic_a.id)
        assert data["name_en"] == "Original Clinic A"
        assert data["phone"] == "+971501111111"

    def test_put_update_allowed_fields(self):
        self.client.force_authenticate(user=self.admin_a)
        payload = {
            "name_en": "Updated Clinic Alpha",
            "name_ar": "عيادة ألفا المحدثة",
            "phone": "+971509999999",
            "whatsapp": "+971508888888",
            "email": "info@alpha.ae",
            "website": "https://alpha.ae",
            "city": "Dubai",
            "google_maps_url": "https://maps.google.com/?q=alpha",
            "google_place_id": "PLACE_ALPHA_123",
        }
        response = self.client.put(self.url, payload)
        assert response.status_code == status.HTTP_200_OK
        self.clinic_a.refresh_from_db()
        assert self.clinic_a.name_en == "Updated Clinic Alpha"
        assert self.clinic_a.phone == "+971509999999"
        assert self.clinic_a.google_place_id == "PLACE_ALPHA_123"

    def test_forbidden_fields_cannot_be_mutated(self):
        self.client.force_authenticate(user=self.admin_a)
        malicious_payload = {
            "name_en": "Attempted Exploit",
            "subscription_tier": "vip",
            "status": "pending",
            "is_featured": True,
            "google_rating": 5.0,
            "moderation_notes": "Self approved",
            "license_number": "MALICIOUS_LIC",
        }
        response = self.client.put(self.url, malicious_payload)
        assert response.status_code == status.HTTP_200_OK

        self.clinic_a.refresh_from_db()
        assert self.clinic_a.name_en == "Attempted Exploit"
        # None of the forbidden fields changed
        assert self.clinic_a.subscription_tier == SubscriptionTier.BASIC
        assert self.clinic_a.status == ClinicStatus.ACTIVE
        assert self.clinic_a.is_featured is False
        assert float(self.clinic_a.google_rating) == 4.5
        assert self.clinic_a.moderation_notes == "Initial review"
        assert self.clinic_a.license_number == ""

    def test_clinic_isolation_between_clinics(self):
        # Admin A updates profile
        self.client.force_authenticate(user=self.admin_a)
        self.client.put(self.url, {"name_en": "Alpha New Name"})

        # Clinic B is unchanged
        self.clinic_b.refresh_from_db()
        assert self.clinic_b.name_en == "Original Clinic B"

        # Staff B gets profile -> sees Clinic B
        self.client.force_authenticate(user=self.staff_b)
        res_b = self.client.get(self.url)
        assert res_b.status_code == status.HTTP_200_OK
        assert res_b.json()["id"] == str(self.clinic_b.id)
