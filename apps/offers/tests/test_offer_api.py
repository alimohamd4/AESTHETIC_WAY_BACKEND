import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicStatus, SubscriptionTier
from apps.media.models import MediaAsset
from apps.offers.models import Offer, OfferStatus


@pytest.mark.django_db
class TestOfferAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:offers:offer-list")

        self.clinic_vip = Clinic.objects.create(
            name_en="VIP Aesthetic Clinic",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.VIP,
            city="Dubai",
        )
        self.clinic_basic = Clinic.objects.create(
            name_en="Basic Care Clinic",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.BASIC,
            city="Sharjah",
        )
        self.clinic_suspended = Clinic.objects.create(
            name_en="Suspended Clinic",
            status=ClinicStatus.SUSPENDED,
            city="Dubai",
        )

        now = timezone.now()

        # Active offer with direct image
        self.offer_active = Offer.objects.create(
            clinic=self.clinic_vip,
            title_en="Summer Glow Botox Package",
            title_ar="باقة البوتوكس الصيفية",
            description_en="Full face botox special offer",
            original_price=1200.00,
            offer_price=799.00,
            image="https://example.com/botox.jpg",
            starts_at=now - timezone.timedelta(days=2),
            ends_at=now + timezone.timedelta(days=10),
            is_active=True,
            status=OfferStatus.ACTIVE,
        )

        # Active offer with media asset
        media = MediaAsset.objects.create(
            media_type="offer_image",
            clinic=self.clinic_basic,
            file="offers/filler.jpg",
            original_filename="filler.jpg",
            file_size=1024,
            mime_type="image/jpeg",
        )
        self.offer_media = Offer.objects.create(
            clinic=self.clinic_basic,
            title_en="Lip Filler Special",
            original_price=1500.00,
            offer_price=1099.00,
            media_asset=media,
            starts_at=now - timezone.timedelta(days=1),
            ends_at=now + timezone.timedelta(days=5),
            is_active=True,
            status=OfferStatus.ACTIVE,
        )

        # Expired offer
        self.offer_expired = Offer.objects.create(
            clinic=self.clinic_vip,
            title_en="Expired New Year Promo",
            original_price=2000.00,
            offer_price=999.00,
            starts_at=now - timezone.timedelta(days=30),
            ends_at=now - timezone.timedelta(days=1),
            is_active=True,
            status=OfferStatus.ACTIVE,
        )

        # Future offer
        self.offer_future = Offer.objects.create(
            clinic=self.clinic_vip,
            title_en="Future Ramadan Promo",
            original_price=2000.00,
            offer_price=999.00,
            starts_at=now + timezone.timedelta(days=5),
            ends_at=now + timezone.timedelta(days=20),
            is_active=True,
            status=OfferStatus.ACTIVE,
        )

        # Inactive offer
        self.offer_inactive = Offer.objects.create(
            clinic=self.clinic_vip,
            title_en="Cancelled Promo",
            original_price=1000.00,
            offer_price=500.00,
            starts_at=now - timezone.timedelta(days=1),
            ends_at=now + timezone.timedelta(days=5),
            is_active=False,
            status=OfferStatus.ACTIVE,
        )

        # Offer from suspended clinic
        self.offer_suspended_clinic = Offer.objects.create(
            clinic=self.clinic_suspended,
            title_en="Offer From Suspended Clinic",
            original_price=1000.00,
            offer_price=500.00,
            starts_at=now - timezone.timedelta(days=1),
            ends_at=now + timezone.timedelta(days=5),
            is_active=True,
            status=OfferStatus.ACTIVE,
        )

    def test_public_offers_list_active_and_valid_only(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        titles = [o["title_en"] for o in response.json()["results"]]
        assert "Summer Glow Botox Package" in titles
        assert "Lip Filler Special" in titles
        assert "Expired New Year Promo" not in titles
        assert "Future Ramadan Promo" not in titles
        assert "Cancelled Promo" not in titles
        assert "Offer From Suspended Clinic" not in titles

    def test_image_url_resolution(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = {o["title_en"]: o for o in response.json()["results"]}
        # Direct URL
        assert results["Summer Glow Botox Package"]["image_url"] == "https://example.com/botox.jpg"
        # MediaAsset URL
        assert "offers/filler.jpg" in results["Lip Filler Special"]["image_url"]

    def test_clinic_filter(self):
        response = self.client.get(self.list_url, {"clinic_id": str(self.clinic_basic.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["title_en"] == "Lip Filler Special"

    def test_offer_detail(self):
        url = reverse("api_v1:offers:offer-detail", kwargs={"id": str(self.offer_active.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["title_en"] == "Summer Glow Botox Package"
        assert data["clinic"]["name_en"] == "VIP Aesthetic Clinic"
        assert float(data["offer_price"]) == 799.00
        assert data["image_url"] == "https://example.com/botox.jpg"

    def test_expired_offer_detail_returns_404(self):
        url = reverse("api_v1:offers:offer-detail", kwargs={"id": str(self.offer_expired.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_private_fields_strictly_forbidden(self):
        response = self.client.get(self.list_url)
        item = response.json()["results"][0]
        assert "status" not in item
        assert "deleted_at" not in item
        assert "is_active" not in item
        assert "subscription_tier" not in item
        # Clinic nested object also must not expose tier
        assert "subscription_tier" not in item["clinic"]
