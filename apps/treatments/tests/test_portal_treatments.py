import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.clinics.models import Clinic, ClinicStatus
from apps.practitioners.models import Practitioner, PractitionerType
from apps.treatments.models import Category, Treatment, TreatmentStatus

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalTreatments:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:clinic_portal_treatments:treatments-list")

        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", status=ClinicStatus.ACTIVE)
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", status=ClinicStatus.ACTIVE)

        self.staff_a = User.objects.create_user(phone="+971501111111", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_b = User.objects.create_user(phone="+971502222222", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.category = Category.objects.create(name_en="Facial Treatments", is_active=True)

        self.doc_a = Practitioner.objects.create(
            clinic=self.clinic_a,
            name_en="Dr. Alpha",
            type=PractitionerType.DOCTOR,
            status="active",
        )
        self.doc_b = Practitioner.objects.create(
            clinic=self.clinic_b,
            name_en="Dr. Beta",
            type=PractitionerType.DOCTOR,
            status="active",
        )

        self.treatment_a = Treatment.objects.create(
            clinic=self.clinic_a,
            category=self.category,
            name_en="Alpha Laser Peel",
            price=1200.00,
            is_active=True,
            status=TreatmentStatus.ACTIVE,
        )
        self.treatment_b = Treatment.objects.create(
            clinic=self.clinic_b,
            category=self.category,
            name_en="Beta Laser Peel",
            price=1400.00,
            is_active=True,
            status=TreatmentStatus.ACTIVE,
        )

    def test_list_treatments_scoped_to_clinic(self):
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.treatment_a.id)

    def test_create_treatment_with_same_clinic_practitioner_success(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "category": str(self.category.id),
            "name_en": "Hydra Glow Treatment",
            "name_ar": "علاج هيدرا جلو",
            "price": "950.00",
            "status": "active",
            "is_active": True,
            "practitioners": [str(self.doc_a.id)],
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        new_id = response.json()["id"]

        treatment = Treatment.objects.get(id=new_id)
        assert treatment.clinic == self.clinic_a
        assert treatment.practitioners.filter(id=self.doc_a.id).exists()

    def test_create_treatment_with_other_clinic_practitioner_rejected(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "category": str(self.category.id),
            "name_en": "Illegal Cross Clinic Treatment",
            "price": "500.00",
            # Practitioner from Clinic B
            "practitioners": [str(self.doc_b.id)],
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "practitioners" in str(response.json())

    def test_retrieve_treatment_detail(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_treatments:treatments-detail", kwargs={"pk": str(self.treatment_a.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name_en"] == "Alpha Laser Peel"

    def test_update_treatment_and_resync_practitioners(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_treatments:treatments-detail", kwargs={"pk": str(self.treatment_a.id)})
        response = self.client.patch(url, {
            "price": "1350.00",
            "practitioners": [str(self.doc_a.id)],
        })
        assert response.status_code == status.HTTP_200_OK
        self.treatment_a.refresh_from_db()
        assert float(self.treatment_a.price) == 1350.00
        assert self.treatment_a.practitioners.filter(id=self.doc_a.id).exists()

    def test_delete_treatment_soft_deletes(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_treatments:treatments-detail", kwargs={"pk": str(self.treatment_a.id)})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.treatment_a.refresh_from_db()
        assert self.treatment_a.deleted_at is not None
        assert self.treatment_a.is_active is False

        res_list = self.client.get(self.list_url)
        assert len(res_list.json()["results"]) == 0

    def test_anti_idor_cross_clinic_access_returns_404(self):
        self.client.force_authenticate(user=self.staff_a)
        url_b = reverse("api_v1:clinic_portal_treatments:treatments-detail", kwargs={"pk": str(self.treatment_b.id)})

        assert self.client.get(url_b).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.patch(url_b, {"price": "1.00"}).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.delete(url_b).status_code == status.HTTP_404_NOT_FOUND

        self.treatment_b.refresh_from_db()
        assert float(self.treatment_b.price) == 1400.00
        assert self.treatment_b.deleted_at is None
