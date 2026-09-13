import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.clinics.models import Clinic, ClinicStatus
from apps.products.models import ContentStatus, Product

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalProducts:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:clinic_portal_products:products-list")

        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", status=ClinicStatus.ACTIVE)
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", status=ClinicStatus.ACTIVE)

        self.staff_a = User.objects.create_user(phone="+971501111111", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_b = User.objects.create_user(phone="+971502222222", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.prod_a = Product.objects.create(
            clinic=self.clinic_a,
            name_en="Alpha Cleanser",
            price=150.00,
            is_active=True,
            status=ContentStatus.ACTIVE,
        )
        self.prod_b = Product.objects.create(
            clinic=self.clinic_b,
            name_en="Beta Cleanser",
            price=180.00,
            is_active=True,
            status=ContentStatus.ACTIVE,
        )

    def test_list_products_scoped_to_clinic(self):
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.prod_a.id)

    def test_create_product_success(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "name_en": "Alpha Sunblock SPF 50",
            "name_ar": "واقي شمس ألفا",
            "price": "220.00",
            "is_active": True,
            "status": "active",
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        new_id = response.json()["id"]

        product = Product.objects.get(id=new_id)
        assert product.clinic == self.clinic_a
        assert float(product.price) == 220.00

    def test_create_product_negative_price_rejected(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "name_en": "Negative Product",
            "price": "-50.00",
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_product_detail(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_products:products-detail", kwargs={"pk": str(self.prod_a.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name_en"] == "Alpha Cleanser"

    def test_update_product(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_products:products-detail", kwargs={"pk": str(self.prod_a.id)})
        response = self.client.patch(url, {"price": "165.00"})
        assert response.status_code == status.HTTP_200_OK
        self.prod_a.refresh_from_db()
        assert float(self.prod_a.price) == 165.00

    def test_delete_product_soft_deletes(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_products:products-detail", kwargs={"pk": str(self.prod_a.id)})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.prod_a.refresh_from_db()
        assert self.prod_a.deleted_at is not None
        assert self.prod_a.is_active is False

        res_list = self.client.get(self.list_url)
        assert len(res_list.json()["results"]) == 0

    def test_anti_idor_cross_clinic_access_returns_404(self):
        self.client.force_authenticate(user=self.staff_a)
        url_b = reverse("api_v1:clinic_portal_products:products-detail", kwargs={"pk": str(self.prod_b.id)})

        assert self.client.get(url_b).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.patch(url_b, {"price": "1.00"}).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.delete(url_b).status_code == status.HTTP_404_NOT_FOUND

        self.prod_b.refresh_from_db()
        assert float(self.prod_b.price) == 180.00
        assert self.prod_b.deleted_at is None
