from unittest.mock import patch
from django.urls import reverse
from django.utils import timezone
from django.db import connection
from rest_framework import status
from rest_framework.test import APITestCase

from apps.clinics.models import Clinic, ClinicStatus, SubscriptionTier
from apps.treatments.models import Category
from apps.media.models import FeaturedAd
from apps.offers.models import Offer

class HomeFeedTests(APITestCase):
    def setUp(self):
        self.url = reverse("api_v1:home:feed")
        
        # Categories
        self.cat1 = Category.objects.create(name_en="Face", slug="face", display_order=1)
        self.cat2 = Category.objects.create(name_en="Body", slug="body", display_order=2)
        
        # Featured Ads
        self.ad_vip = FeaturedAd.objects.create(image="http://example.com/vip.png", subscription_tier="vip", display_order=1)
        self.ad_basic = FeaturedAd.objects.create(image="http://example.com/basic.png", subscription_tier="basic", display_order=2)

        # Clinics
        self.clinic_vip = Clinic.objects.create(
            name_en="VIP Clinic",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.VIP,
            google_rating=4.9,
            city="Dubai",
            latitude=25.2048,
            longitude=55.2708,
            license_number="LIC-1",
        )
        self.clinic_featured = Clinic.objects.create(
            name_en="Featured Clinic",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.FEATURED,
            google_rating=4.5,
            city="Dubai",
            latitude=25.2100,
            longitude=55.2800,
            license_number="LIC-2",
        )
        self.clinic_basic = Clinic.objects.create(
            name_en="Basic Clinic",
            status=ClinicStatus.ACTIVE,
            subscription_tier=SubscriptionTier.BASIC,
            google_rating=4.8, # higher rating but lower tier
            city="Abu Dhabi",
            latitude=24.4539,
            longitude=54.3773,
            license_number="LIC-3",
        )
        self.clinic_suspended = Clinic.objects.create(
            name_en="Suspended Clinic",
            status=ClinicStatus.SUSPENDED,
            subscription_tier=SubscriptionTier.VIP,
            city="Dubai",
            latitude=25.2000,
            longitude=55.2000,
        )

        now = timezone.now()
        
        # Offers
        self.active_offer = Offer.objects.create(
            clinic=self.clinic_vip,
            title_en="Summer Glow",
            original_price=1000,
            offer_price=800,
            starts_at=now - timezone.timedelta(days=1),
            ends_at=now + timezone.timedelta(days=10),
            is_active=True
        )
        self.inactive_offer = Offer.objects.create(
            clinic=self.clinic_vip,
            title_en="Winter Sale",
            original_price=1000,
            offer_price=800,
            starts_at=now - timezone.timedelta(days=10),
            ends_at=now - timezone.timedelta(days=1), # expired
            is_active=True
        )

    def test_feed_success_no_location(self):
        """Test missing location falls back to city filtering if city is provided, or just tier/rating ranking."""
        response = self.client.get(self.url, {"city": "Dubai"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        
        # Check suspended clinics are excluded
        clinics = data["nearby_clinics"]
        clinic_names = [c["name_en"] for c in clinics]
        self.assertNotIn("Suspended Clinic", clinic_names)
        
        # Check city filter applied (Abu Dhabi clinic should be excluded)
        self.assertNotIn("Basic Clinic", clinic_names)

        # Check Tier Ordering (VIP first, then Featured)
        self.assertEqual(clinics[0]["name_en"], "VIP Clinic")
        self.assertEqual(clinics[1]["name_en"], "Featured Clinic")

        # Check serialization (no internal fields)
        self.assertNotIn("subscription_tier", clinics[0])
        self.assertNotIn("license_number", clinics[0])
        self.assertNotIn("status", clinics[0])
        self.assertNotIn("moderation_notes", clinics[0])

        # Check inactive offers excluded
        offers = data["active_offers"]
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["title_en"], "Summer Glow")

    @patch("apps.home.views.RawSQL")
    def test_feed_distance_ranking(self, mock_raw_sql):
        """Test that providing latitude and longitude triggers distance calculation and ranking."""
        # We mock RawSQL to just return 100 so the DB doesn't complain if PostGIS isn't installed in the test DB
        from django.db.models import Value, FloatField
        mock_raw_sql.return_value = Value(100.0, output_field=FloatField())

        response = self.client.get(self.url, {"latitude": "25.2000", "longitude": "55.2700"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        clinics = data["nearby_clinics"]
        
        # Check that distance is serialized
        self.assertIn("distance", clinics[0])
        
        # Verify call was made
        self.assertTrue(mock_raw_sql.called)

