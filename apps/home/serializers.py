from rest_framework import serializers

from apps.treatments.models import Category
from apps.offers.models import Offer
from apps.media.models import FeaturedAd
from apps.clinics.models import Clinic


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name_en", "name_ar", "slug", "icon"]


class PublicClinicSerializer(serializers.ModelSerializer):
    """
    Patient-facing clinic serializer.
    STRICTLY EXCLUDES internal fields: subscription_tier, moderation_*, license_*.
    """
    distance = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = Clinic
        fields = [
            "id",
            "name_en",
            "name_ar",
            "slug",
            "description_en",
            "description_ar",
            "phone",
            "whatsapp",
            "email",
            "website",
            "address_en",
            "address_ar",
            "city",
            "emirate",
            "latitude",
            "longitude",
            "logo",
            "cover_image",
            "is_featured",
            "google_rating",
            "distance",
        ]


class OfferSerializer(serializers.ModelSerializer):
    clinic = PublicClinicSerializer(read_only=True)

    class Meta:
        model = Offer
        fields = [
            "id",
            "clinic",
            "title_en",
            "title_ar",
            "description_en",
            "description_ar",
            "original_price",
            "offer_price",
            "starts_at",
            "ends_at",
        ]


class FeaturedAdSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeaturedAd
        fields = ["id", "image", "link"]

