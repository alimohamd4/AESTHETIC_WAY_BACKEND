from rest_framework import serializers

from apps.clinics.models import Clinic
from apps.offers.models import Offer


class PublicOfferClinicSummarySerializer(serializers.ModelSerializer):
    """Public clinic summary for offer responses."""

    class Meta:
        model = Clinic
        fields = [
            "id",
            "name_en",
            "name_ar",
            "slug",
            "city",
            "logo",
        ]
        read_only_fields = fields


class PublicOfferSerializer(serializers.ModelSerializer):
    """
    Public serializer for promotional offers.
    Resolves image_url dynamically via model property.
    STRICT SECURITY EXCLUSION:
    - internal subscription tier
    - moderation status, deleted_at
    """

    clinic = PublicOfferClinicSummarySerializer(read_only=True)
    image_url = serializers.CharField(read_only=True)

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
            "image_url",
        ]
        read_only_fields = fields
