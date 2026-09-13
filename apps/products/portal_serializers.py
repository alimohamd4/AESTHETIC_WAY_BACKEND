from rest_framework import serializers

from apps.media.models import MediaAsset
from apps.products.models import ContentStatus, Product


class ClinicProductPortalSerializer(serializers.ModelSerializer):
    """
    Serializer for managing retail and skincare products in the clinic portal.
    """

    image_url = serializers.CharField(read_only=True)
    media_asset = serializers.PrimaryKeyRelatedField(
        queryset=MediaAsset.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name_en",
            "name_ar",
            "description_en",
            "description_ar",
            "price",
            "image",
            "media_asset",
            "image_url",
            "status",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "image_url", "created_at", "updated_at"]

    def validate_status(self, value):
        if value not in ContentStatus.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {ContentStatus.values}"
            )
        return value

    def validate_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value
