import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.clinics.models import Clinic, ClinicStatus
from apps.offers.models import Offer, OfferStatus

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalOffers:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:clinic_portal_offers:offers-list")

        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", status=ClinicStatus.ACTIVE)
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", status=ClinicStatus.ACTIVE)

        self.staff_a = User.objects.create_user(phone="+971501111111", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_b = User.objects.create_user(phone="+971502222222", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        now = timezone.now()
        self.offer_a = Offer.objects.create(
            clinic=self.clinic_a,
            title_en="Alpha Botox Promo",
            original_price=1500.00,
            offer_price=999.00,
            starts_at=now,
            ends_at=now + timezone.timedelta(days=10),
            is_active=True,
            status=OfferStatus.ACTIVE,
        )
        self.offer_b = Offer.objects.create(
            clinic=self.clinic_b,
            title_en="Beta Filler Promo",
            original_price=1800.00,
            offer_price=1200.00,
            starts_at=now,
            ends_at=now + timezone.timedelta(days=10),
            is_active=True,
            status=OfferStatus.ACTIVE,
        )

    def test_list_offers_scoped_to_clinic(self):
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.offer_a.id)

    def test_create_offer_success(self):
        self.client.force_authenticate(user=self.staff_a)
        now = timezone.now()
        payload = {
            "title_en": "Laser Package",
            "title_ar": "باقة الليزر",
            "original_price": "2000.00",
            "offer_price": "1400.00",
            "starts_at": now.isoformat(),
            "ends_at": (now + timezone.timedelta(days=14)).isoformat(),
            "status": "active",
            "is_active": True,
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        new_id = response.json()["id"]

        offer = Offer.objects.get(id=new_id)
        assert offer.clinic == self.clinic_a
        assert float(offer.offer_price) == 1400.00

    def test_create_offer_invalid_dates_rejected(self):
        self.client.force_authenticate(user=self.staff_a)
        now = timezone.now()
        payload = {
            "title_en": "Backwards Offer",
            "original_price": "1000.00",
            "offer_price": "800.00",
            "starts_at": now.isoformat(),
            "ends_at": (now - timezone.timedelta(days=1)).isoformat(),  # End before start
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ends_at" in str(response.json())

    def test_retrieve_offer_detail(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_offers:offers-detail", kwargs={"pk": str(self.offer_a.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title_en"] == "Alpha Botox Promo"

    def test_update_offer(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_offers:offers-detail", kwargs={"pk": str(self.offer_a.id)})
        response = self.client.patch(url, {"offer_price": "899.00"})
        assert response.status_code == status.HTTP_200_OK
        self.offer_a.refresh_from_db()
        assert float(self.offer_a.offer_price) == 899.00

    def test_delete_offer_soft_deletes(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_offers:offers-detail", kwargs={"pk": str(self.offer_a.id)})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.offer_a.refresh_from_db()
        assert self.offer_a.deleted_at is not None
        assert self.offer_a.is_active is False

        res_list = self.client.get(self.list_url)
        assert len(res_list.json()["results"]) == 0

    def test_anti_idor_cross_clinic_access_returns_404(self):
        self.client.force_authenticate(user=self.staff_a)
        url_b = reverse("api_v1:clinic_portal_offers:offers-detail", kwargs={"pk": str(self.offer_b.id)})

        assert self.client.get(url_b).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.patch(url_b, {"offer_price": "10.00"}).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.delete(url_b).status_code == status.HTTP_404_NOT_FOUND

        self.offer_b.refresh_from_db()
        assert float(self.offer_b.offer_price) == 1200.00
        assert self.offer_b.deleted_at is None
