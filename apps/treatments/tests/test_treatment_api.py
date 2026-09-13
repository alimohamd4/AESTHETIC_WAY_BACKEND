import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicStatus
from apps.practitioners.models import Practitioner, PractitionerType
from apps.treatments.models import (
    Category,
    PractitionerTreatment,
    Treatment,
    TreatmentStatus,
)


@pytest.mark.django_db
class TestTreatmentAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:treatments:treatment-list")

        self.clinic1 = Clinic.objects.create(
            name_en="Clinic Alpha",
            status=ClinicStatus.ACTIVE,
            city="Dubai",
        )
        self.clinic2 = Clinic.objects.create(
            name_en="Clinic Beta",
            status=ClinicStatus.ACTIVE,
            city="Abu Dhabi",
        )
        self.clinic_suspended = Clinic.objects.create(
            name_en="Suspended Clinic",
            status=ClinicStatus.SUSPENDED,
            city="Dubai",
        )

        self.cat_laser = Category.objects.create(
            name_en="Laser Hair Removal",
            slug="laser-hair-removal",
            is_active=True,
        )
        self.cat_injectables = Category.objects.create(
            name_en="Injectables",
            slug="injectables",
            is_active=True,
        )
        self.cat_inactive = Category.objects.create(
            name_en="Inactive Category",
            slug="inactive-category",
            is_active=False,
        )

        self.doctor_alpha = Practitioner.objects.create(
            clinic=self.clinic1,
            name_en="Dr. Alpha",
            type=PractitionerType.DOCTOR,
            status="active",
        )

        # Active Treatment Alpha Laser
        self.treatment_alpha = Treatment.objects.create(
            clinic=self.clinic1,
            category=self.cat_laser,
            name_en="Full Body Laser",
            name_ar="ليزر كامل الجسم",
            description_en="Advanced candela laser session",
            price=1200.00,
            is_active=True,
            status=TreatmentStatus.ACTIVE,
        )
        PractitionerTreatment.objects.create(
            practitioner=self.doctor_alpha,
            treatment=self.treatment_alpha,
        )

        # Active Treatment Beta Injectable
        self.treatment_beta = Treatment.objects.create(
            clinic=self.clinic2,
            category=self.cat_injectables,
            name_en="Lip Filler 1ml",
            price=1500.00,
            is_active=True,
            status=TreatmentStatus.ACTIVE,
        )

        # Inactive Treatment
        self.treatment_inactive = Treatment.objects.create(
            clinic=self.clinic1,
            category=self.cat_laser,
            name_en="Discontinued Treatment",
            is_active=False,
            status=TreatmentStatus.ACTIVE,
        )

        # Soft-deleted Treatment
        self.treatment_deleted = Treatment.objects.create(
            clinic=self.clinic1,
            category=self.cat_laser,
            name_en="Deleted Treatment",
            is_active=True,
            status=TreatmentStatus.ACTIVE,
            deleted_at=timezone.now(),
        )

        # Treatment in inactive category
        self.treatment_inactive_cat = Treatment.objects.create(
            clinic=self.clinic1,
            category=self.cat_inactive,
            name_en="Hidden Category Treatment",
            is_active=True,
            status=TreatmentStatus.ACTIVE,
        )

        # Treatment in suspended clinic
        self.treatment_suspended_clinic = Treatment.objects.create(
            clinic=self.clinic_suspended,
            category=self.cat_laser,
            name_en="Suspended Clinic Treatment",
            is_active=True,
            status=TreatmentStatus.ACTIVE,
        )

    def test_treatment_list_active_only(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        names = [t["name_en"] for t in response.json()["results"]]
        assert "Full Body Laser" in names
        assert "Lip Filler 1ml" in names
        assert "Discontinued Treatment" not in names
        assert "Deleted Treatment" not in names
        assert "Hidden Category Treatment" not in names
        assert "Suspended Clinic Treatment" not in names

    def test_category_filtering(self):
        response = self.client.get(self.list_url, {"category_id": str(self.cat_laser.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Full Body Laser"

    def test_clinic_filtering(self):
        response = self.client.get(self.list_url, {"clinic_id": str(self.clinic2.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Lip Filler 1ml"

    def test_practitioner_filtering(self):
        response = self.client.get(self.list_url, {"practitioner_id": str(self.doctor_alpha.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Full Body Laser"

    def test_search_by_text(self):
        response = self.client.get(self.list_url, {"search": "candela"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Full Body Laser"

    def test_treatment_detail_and_cross_clinic_isolation(self):
        url = reverse("api_v1:treatments:treatment-detail", kwargs={"id": str(self.treatment_alpha.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name_en"] == "Full Body Laser"
        assert data["clinic"]["name_en"] == "Clinic Alpha"
        assert data["category"]["name_en"] == "Laser Hair Removal"
        assert len(data["practitioners"]) == 1
        assert data["practitioners"][0]["name_en"] == "Dr. Alpha"

    def test_private_fields_not_exposed(self):
        response = self.client.get(self.list_url)
        item = response.json()["results"][0]
        assert "status" not in item
        assert "deleted_at" not in item
        assert "is_active" not in item

    def test_inactive_treatment_detail_returns_404(self):
        url = reverse("api_v1:treatments:treatment-detail", kwargs={"id": str(self.treatment_inactive.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
