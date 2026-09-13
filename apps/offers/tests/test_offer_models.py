from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.clinics.models import Clinic
from apps.media.models import MediaAsset, MediaType
from apps.offers.models import Offer, OfferStatus


class OfferModelTests(TestCase):
    def setUp(self):
        self.clinic = Clinic.objects.create(name_en="Beauty Center", city="Abu Dhabi")
        self.now = timezone.now()

    def test_offer_image_url_direct_and_media_asset(self):
        """Offer image can be set directly via URL or resolved from a MediaAsset."""
        # Direct URL
        offer1 = Offer.objects.create(
            clinic=self.clinic,
            title_en="Hydrafacial Special",
            original_price=1000.00,
            offer_price=650.00,
            image="https://cdn.example.com/hydra.jpg",
            starts_at=self.now,
            ends_at=self.now + timedelta(days=14),
        )
        self.assertEqual(offer1.image_url, "https://cdn.example.com/hydra.jpg")

        # Via MediaAsset
        media_asset = MediaAsset.objects.create(
            media_type=MediaType.OFFER_IMAGE,
            clinic=self.clinic,
            original_filename="promo.jpg",
            file_size=50000,
            mime_type="image/jpeg",
        )
        offer2 = Offer.objects.create(
            clinic=self.clinic,
            title_en="Laser Package",
            original_price=2000.00,
            offer_price=1500.00,
            media_asset=media_asset,
            starts_at=self.now,
            ends_at=self.now + timedelta(days=30),
        )
        self.assertEqual(offer2.media_asset, media_asset)
        self.assertEqual(offer2.status, OfferStatus.ACTIVE)
