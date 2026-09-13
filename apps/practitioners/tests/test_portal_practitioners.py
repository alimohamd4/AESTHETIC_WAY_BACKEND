import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.clinics.models import Clinic, ClinicStatus
from apps.practitioners.models import (
    Practitioner,
    PractitionerStatus,
    PractitionerType,
)

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalPractitioners:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:clinic_portal_practitioners:practitioners-list")

        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", status=ClinicStatus.ACTIVE)
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", status=ClinicStatus.ACTIVE)

        self.staff_a = User.objects.create_user(phone="+971501111111", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_b = User.objects.create_user(phone="+971502222222", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.doc_a = Practitioner.objects.create(
            clinic=self.clinic_a,
            name_en="Dr. Alpha Specialist",
            type=PractitionerType.DOCTOR,
            status=PractitionerStatus.ACTIVE,
            license_number="LIC-ALPHA-1",
        )
        self.doc_b = Practitioner.objects.create(
            clinic=self.clinic_b,
            name_en="Dr. Beta Specialist",
            type=PractitionerType.DOCTOR,
            status=PractitionerStatus.ACTIVE,
            license_number="LIC-BETA-1",
        )

    def test_list_practitioners_scoped_to_clinic(self):
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.doc_a.id)
        assert results[0]["name_en"] == "Dr. Alpha Specialist"

    def test_create_practitioner_success(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "name_en": "Nurse Sarah",
            "name_ar": "الممرضة سارة",
            "title_en": "Lead Aesthetic Nurse",
            "type": "nurse",
            "license_number": "DHA-RN-5555",
            "license_authority": "DHA",
            "status": "active",
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        new_id = response.json()["id"]

        practitioner = Practitioner.objects.get(id=new_id)
        assert practitioner.clinic == self.clinic_a
        assert practitioner.type == PractitionerType.NURSE
        assert practitioner.license_number == "DHA-RN-5555"

    def test_create_practitioner_invalid_type_rejected(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "name_en": "Therapist Tom",
            "type": "unlicensed_helper",
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_practitioner_detail(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_practitioners:practitioners-detail", kwargs={"pk": str(self.doc_a.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["license_number"] == "LIC-ALPHA-1"

    def test_update_practitioner(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_practitioners:practitioners-detail", kwargs={"pk": str(self.doc_a.id)})
        response = self.client.patch(url, {"speciality_en": "Dermatology & Laser"})
        assert response.status_code == status.HTTP_200_OK
        self.doc_a.refresh_from_db()
        assert self.doc_a.speciality_en == "Dermatology & Laser"

    def test_delete_practitioner_soft_deletes(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_practitioners:practitioners-detail", kwargs={"pk": str(self.doc_a.id)})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.doc_a.refresh_from_db()
        assert self.doc_a.deleted_at is not None
        assert self.doc_a.status == PractitionerStatus.INACTIVE

        res_list = self.client.get(self.list_url)
        assert len(res_list.json()["results"]) == 0

    def test_anti_idor_cross_clinic_access_returns_404(self):
        self.client.force_authenticate(user=self.staff_a)
        url_b = reverse("api_v1:clinic_portal_practitioners:practitioners-detail", kwargs={"pk": str(self.doc_b.id)})

        assert self.client.get(url_b).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.patch(url_b, {"name_en": "Compromised"}).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.delete(url_b).status_code == status.HTTP_404_NOT_FOUND

        self.doc_b.refresh_from_db()
        assert self.doc_b.name_en == "Dr. Beta Specialist"
        assert self.doc_b.deleted_at is None
