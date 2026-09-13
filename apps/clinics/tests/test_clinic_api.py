import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicBranch, ClinicStatus, SubscriptionTier
from apps.practitioners.models import Practitioner, PractitionerType
from apps.treatments.models import Category, Treatment


@pytest.mark.django_db
class TestClinicAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:clinics:clinic-list")

        # Active VIP clinic in Dubai
        self.clinic_vip = Clinic.objects.create(
            name_en="Dubai VIP Aesthetics",
            name_ar="دبي في اي بي للتجميل",
            slug="dubai-vip-aesthetics",
            description_en="Premier cosmetic clinic in Dubai",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.VIP,
            city="Dubai",
            emirate="Dubai",
            latitude=25.2048,
            longitude=55.2708,
            google_rating=4.9,
            license_number="DHA-CL-9999",
            license_authority="Dubai Health Authority",
            moderation_notes="Internal review complete.",
        )
        self.branch_vip = ClinicBranch.objects.create(
            clinic=self.clinic_vip,
            name_en="Downtown Branch",
            city="Dubai",
            is_main_branch=True,
            is_active=True,
        )

        # Active Featured clinic in Dubai
        self.clinic_featured = Clinic.objects.create(
            name_en="Jumeirah Beauty Center",
            name_ar="مركز جميرا للتجميل",
            slug="jumeirah-beauty-center",
            description_en="Specialized aesthetic clinic",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.FEATURED,
            city="Dubai",
            emirate="Dubai",
            latitude=25.2100,
            longitude=55.2800,
            google_rating=4.5,
            license_number="DHA-CL-8888",
        )

        # Active Basic clinic in Abu Dhabi
        self.clinic_basic = Clinic.objects.create(
            name_en="Abu Dhabi Derma",
            name_ar="أبوظبي للجلدية",
            slug="abu-dhabi-derma",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.BASIC,
            city="Abu Dhabi",
            emirate="Abu Dhabi",
            latitude=24.4539,
            longitude=54.3773,
            google_rating=5.0,
            license_number="DOH-CL-7777",
        )

        # Suspended clinic
        self.clinic_suspended = Clinic.objects.create(
            name_en="Suspended Clinic",
            status=ClinicStatus.SUSPENDED,
            subscription_tier=SubscriptionTier.VIP,
            city="Dubai",
        )

        # Soft-deleted clinic
        self.clinic_deleted = Clinic.objects.create(
            name_en="Deleted Clinic",
            status=ClinicStatus.ACTIVE,
            deleted_at=timezone.now(),
            city="Dubai",
        )

        # Category and treatments for category filter testing
        self.category_skin = Category.objects.create(
            name_en="Skin Care",
            slug="skin-care",
            display_order=1,
            is_active=True,
        )
        self.treatment_vip = Treatment.objects.create(
            clinic=self.clinic_vip,
            category=self.category_skin,
            name_en="HydraFacial Glow",
            is_active=True,
            status="active",
        )

        # Practitioner on VIP clinic
        self.practitioner_vip = Practitioner.objects.create(
            clinic=self.clinic_vip,
            name_en="Dr. Fatima",
            type=PractitionerType.DOCTOR,
            status="active",
            license_number="LIC-FATIMA-123",
        )

    def test_public_clinic_list_excludes_inactive_and_deleted(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        names = [c["name_en"] for c in response.json()["results"]]
        assert "Dubai VIP Aesthetics" in names
        assert "Jumeirah Beauty Center" in names
        assert "Abu Dhabi Derma" in names
        assert "Suspended Clinic" not in names
        assert "Deleted Clinic" not in names

    def test_tier_ordering(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        # VIP first, then Featured, then Basic (even though Basic has rating 5.0 vs VIP 4.9)
        assert results[0]["name_en"] == "Dubai VIP Aesthetics"
        assert results[1]["name_en"] == "Jumeirah Beauty Center"
        assert results[2]["name_en"] == "Abu Dhabi Derma"

    def test_city_filter(self):
        response = self.client.get(self.list_url, {"city": "Abu Dhabi"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Abu Dhabi Derma"

    def test_category_filter(self):
        response = self.client.get(self.list_url, {"category_id": str(self.category_skin.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        names = [c["name_en"] for c in results]
        assert "Dubai VIP Aesthetics" in names
        assert "Jumeirah Beauty Center" not in names

    def test_search_by_name(self):
        response = self.client.get(self.list_url, {"search": "Jumeirah"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Jumeirah Beauty Center"

    def test_distance_ordering_with_geo_params(self):
        # Coordinates very close to Jumeirah (25.2100, 55.2800)
        response = self.client.get(self.list_url, {"lat": "25.2100", "lng": "55.2800"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        # VIP is still tier 1, so VIP comes first due to tier priority
        assert results[0]["name_en"] == "Dubai VIP Aesthetics"
        # Distance should be annotated
        assert "distance" in results[0]

    def test_private_fields_strictly_scrubbed_from_list(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        clinic_data = response.json()["results"][0]
        forbidden_fields = [
            "subscription_tier",
            "license_number",
            "license_authority",
            "moderation_notes",
            "moderated_by",
            "moderated_at",
            "status",
            "deleted_at",
        ]
        for field in forbidden_fields:
            assert field not in clinic_data, f"Forbidden field '{field}' was exposed in public list!"

    def test_public_clinic_detail_by_id_and_slug(self):
        # By UUID
        url_id = reverse("api_v1:clinics:clinic-detail", kwargs={"id": str(self.clinic_vip.id)})
        res_id = self.client.get(url_id)
        assert res_id.status_code == status.HTTP_200_OK
        data_id = res_id.json()
        assert data_id["name_en"] == "Dubai VIP Aesthetics"
        assert len(data_id["branches"]) == 1
        assert data_id["branches"][0]["name_en"] == "Downtown Branch"
        assert len(data_id["practitioners"]) == 1
        assert data_id["practitioners"][0]["name_en"] == "Dr. Fatima"
        assert len(data_id["treatments"]) == 1
        assert data_id["treatments"][0]["name_en"] == "HydraFacial Glow"

        # By slug
        url_slug = reverse("api_v1:clinics:clinic-detail", kwargs={"id": self.clinic_vip.slug})
        res_slug = self.client.get(url_slug)
        assert res_slug.status_code == status.HTTP_200_OK
        assert res_slug.json()["id"] == str(self.clinic_vip.id)

    def test_private_fields_strictly_scrubbed_from_detail(self):
        url = reverse("api_v1:clinics:clinic-detail", kwargs={"id": str(self.clinic_vip.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        forbidden_fields = [
            "subscription_tier",
            "license_number",
            "license_authority",
            "moderation_notes",
            "moderated_by",
            "moderated_at",
            "status",
            "deleted_at",
        ]
        for field in forbidden_fields:
            assert field not in data, f"Forbidden field '{field}' was exposed in public detail!"

        # Check practitioner nested serialization also does not leak license
        practitioner = data["practitioners"][0]
        assert "license_number" not in practitioner
        assert "license_authority" not in practitioner

    def test_suspended_clinic_detail_returns_404(self):
        url = reverse("api_v1:clinics:clinic-detail", kwargs={"id": str(self.clinic_suspended.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
