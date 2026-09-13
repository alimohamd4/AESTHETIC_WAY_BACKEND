from rest_framework import serializers

from apps.clinics.models import Clinic
from apps.products.models import Product


class PublicProductClinicSummarySerializer(serializers.ModelSerializer):
    """Public clinic summary for product responses."""

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


class PublicProductSerializer(serializers.ModelSerializer):
    """
    Public serializer for clinic products (inquiry only).
    STRICT SECURITY EXCLUSION:
    - No e-commerce or patient ownership concept
    - No internal moderation fields (status, deleted_at)
    """

    clinic = PublicProductClinicSummarySerializer(read_only=True)
    image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "clinic",
            "name_en",
            "name_ar",
            "description_en",
            "description_ar",
            "price",
            "image_url",
            "created_at",
        ]
        read_only_fields = fields
