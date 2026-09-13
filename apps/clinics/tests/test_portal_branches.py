import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.clinics.models import Clinic, ClinicBranch, ClinicStatus

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalBranches:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:clinic_portal_branches:branches-list")

        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", status=ClinicStatus.ACTIVE)
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", status=ClinicStatus.ACTIVE)

        self.staff_a = User.objects.create_user(phone="+971501111111", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_b = User.objects.create_user(phone="+971502222222", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        # Branch for Clinic A
        self.branch_a = ClinicBranch.objects.create(
            clinic=self.clinic_a,
            name_en="Alpha Downtown Branch",
            city="Dubai",
            is_main_branch=True,
            is_active=True,
        )

        # Branch for Clinic B
        self.branch_b = ClinicBranch.objects.create(
            clinic=self.clinic_b,
            name_en="Beta Marina Branch",
            city="Dubai",
            is_main_branch=True,
            is_active=True,
        )

    def test_list_branches_scoped_to_clinic(self):
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.branch_a.id)
        assert results[0]["name_en"] == "Alpha Downtown Branch"

    def test_create_branch_auto_attaches_to_clinic(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "name_en": "Alpha Jumeirah Branch",
            "name_ar": "فرع جميرا ألفا",
            "address_en": "Jumeirah Beach Road",
            "city": "Dubai",
            "phone": "+97143333333",
            "google_place_id": "PLACE_ALPHA_JUMEIRAH",
            # Attempting to assign to clinic B must be ignored/safely scoped
            "clinic": str(self.clinic_b.id),
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        new_branch_id = response.json()["id"]

        branch = ClinicBranch.objects.get(id=new_branch_id)
        assert branch.clinic == self.clinic_a  # Derived from auth, not payload
        assert branch.name_en == "Alpha Jumeirah Branch"
        assert branch.google_place_id == "PLACE_ALPHA_JUMEIRAH"

    def test_retrieve_branch_detail(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_branches:branches-detail", kwargs={"pk": str(self.branch_a.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name_en"] == "Alpha Downtown Branch"

    def test_update_branch(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_branches:branches-detail", kwargs={"pk": str(self.branch_a.id)})
        response = self.client.patch(url, {"name_en": "Alpha Updated Branch"})
        assert response.status_code == status.HTTP_200_OK
        self.branch_a.refresh_from_db()
        assert self.branch_a.name_en == "Alpha Updated Branch"

    def test_delete_branch_soft_deletes(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_branches:branches-detail", kwargs={"pk": str(self.branch_a.id)})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.branch_a.refresh_from_db()
        assert self.branch_a.deleted_at is not None
        assert self.branch_a.is_active is False

        # Deleted branch no longer appears in portal list
        res_list = self.client.get(self.list_url)
        assert len(res_list.json()["results"]) == 0

    def test_anti_idor_cross_clinic_access_returns_404(self):
        # Staff A attempts to view, update, or delete Clinic B's branch
        self.client.force_authenticate(user=self.staff_a)
        url_b = reverse("api_v1:clinic_portal_branches:branches-detail", kwargs={"pk": str(self.branch_b.id)})

        assert self.client.get(url_b).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.patch(url_b, {"name_en": "Hacked"}).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.delete(url_b).status_code == status.HTTP_404_NOT_FOUND

        # Clinic B's branch is completely untouched
        self.branch_b.refresh_from_db()
        assert self.branch_b.name_en == "Beta Marina Branch"
        assert self.branch_b.deleted_at is None
