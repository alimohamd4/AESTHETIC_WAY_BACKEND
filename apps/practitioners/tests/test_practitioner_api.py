import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicStatus
from apps.practitioners.models import (
    Practitioner,
    PractitionerStatus,
    PractitionerType,
)
from apps.treatments.models import Category, PractitionerTreatment, Treatment


@pytest.mark.django_db
class TestPractitionerAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:practitioners:practitioner-list")

        self.clinic_active = Clinic.objects.create(
            name_en="Active Clinic",
            status=ClinicStatus.ACTIVE,
            city="Dubai",
        )
        self.clinic_suspended = Clinic.objects.create(
            name_en="Suspended Clinic",
            status=ClinicStatus.SUSPENDED,
            city="Dubai",
        )

        self.category = Category.objects.create(name_en="Injectables", is_active=True)
        self.treatment = Treatment.objects.create(
            clinic=self.clinic_active,
            category=self.category,
            name_en="Botox Treatment",
            is_active=True,
            status="active",
        )

        # Active Doctor
        self.doctor = Practitioner.objects.create(
            clinic=self.clinic_active,
            name_en="Dr. Ahmed Mansoor",
            name_ar="د. أحمد منصور",
            title_en="Consultant Dermatologist",
            type=PractitionerType.DOCTOR,
            status=PractitionerStatus.ACTIVE,
            license_number="DHA-DOC-12345",
            license_authority="Dubai Health Authority",
            display_order=1,
        )
        PractitionerTreatment.objects.create(
            practitioner=self.doctor,
            treatment=self.treatment,
        )

        # Active Nurse
        self.nurse = Practitioner.objects.create(
            clinic=self.clinic_active,
            name_en="Nurse Sarah Smith",
            type=PractitionerType.NURSE,
            status=PractitionerStatus.ACTIVE,
            license_number="DHA-NUR-9876",
            display_order=2,
        )

        # Inactive Practitioner
        self.practitioner_inactive = Practitioner.objects.create(
            clinic=self.clinic_active,
            name_en="Inactive Practitioner",
            type=PractitionerType.LICENSED_PROFESSIONAL,
            status=PractitionerStatus.INACTIVE,
        )

        # Practitioner in suspended clinic
        self.practitioner_suspended_clinic = Practitioner.objects.create(
            clinic=self.clinic_suspended,
            name_en="Dr. Suspended Clinic",
            type=PractitionerType.DOCTOR,
            status=PractitionerStatus.ACTIVE,
        )

    def test_public_practitioner_list_excludes_inactive_and_suspended_clinic(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        names = [p["name_en"] for p in response.json()["results"]]
        assert "Dr. Ahmed Mansoor" in names
        assert "Nurse Sarah Smith" in names
        assert "Inactive Practitioner" not in names
        assert "Dr. Suspended Clinic" not in names

    def test_type_filtering(self):
        # Filter doctor
        res_doc = self.client.get(self.list_url, {"type": "doctor"})
        assert res_doc.status_code == status.HTTP_200_OK
        doc_names = [p["name_en"] for p in res_doc.json()["results"]]
        assert "Dr. Ahmed Mansoor" in doc_names
        assert "Nurse Sarah Smith" not in doc_names

        # Filter nurse
        res_nurse = self.client.get(self.list_url, {"type": "nurse"})
        assert res_nurse.status_code == status.HTTP_200_OK
        nurse_names = [p["name_en"] for p in res_nurse.json()["results"]]
        assert "Nurse Sarah Smith" in nurse_names
        assert "Dr. Ahmed Mansoor" not in nurse_names

    def test_clinic_filtering(self):
        response = self.client.get(self.list_url, {"clinic_id": str(self.clinic_active.id)})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["results"]) == 2

    def test_treatment_filtering(self):
        response = self.client.get(self.list_url, {"treatment_id": str(self.treatment.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Dr. Ahmed Mansoor"

    def test_practitioner_detail(self):
        url = reverse("api_v1:practitioners:practitioner-detail", kwargs={"id": str(self.doctor.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name_en"] == "Dr. Ahmed Mansoor"
        assert data["clinic"]["name_en"] == "Active Clinic"
        assert len(data["treatments"]) == 1
        assert data["treatments"][0]["name_en"] == "Botox Treatment"

    def test_license_fields_strictly_forbidden(self):
        # List
        res_list = self.client.get(self.list_url)
        item = res_list.json()["results"][0]
        assert "license_number" not in item
        assert "license_authority" not in item
        assert "status" not in item

        # Detail
        url = reverse("api_v1:practitioners:practitioner-detail", kwargs={"id": str(self.doctor.id)})
        res_detail = self.client.get(url)
        detail_item = res_detail.json()
        assert "license_number" not in detail_item
        assert "license_authority" not in detail_item
        assert "status" not in detail_item

    def test_inactive_practitioner_detail_returns_404(self):
        url = reverse("api_v1:practitioners:practitioner-detail", kwargs={"id": str(self.practitioner_inactive.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
