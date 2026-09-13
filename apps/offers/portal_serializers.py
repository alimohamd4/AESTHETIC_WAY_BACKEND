from rest_framework import serializers

from apps.media.models import MediaAsset
from apps.offers.models import Offer, OfferStatus


class ClinicOfferPortalSerializer(serializers.ModelSerializer):
    """
    Serializer for managing promotional offers in the clinic portal.
    """

    image_url = serializers.CharField(read_only=True)
    media_asset = serializers.PrimaryKeyRelatedField(
        queryset=MediaAsset.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Offer
        fields = [
            "id",
            "title_en",
            "title_ar",
            "description_en",
            "description_ar",
            "original_price",
            "offer_price",
            "starts_at",
            "ends_at",
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
        if value not in OfferStatus.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {OfferStatus.values}"
            )
        return value

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))

        if starts_at and ends_at and ends_at < starts_at:
            raise serializers.ValidationError(
                {"ends_at": "Offer end date cannot be earlier than the start date."}
            )

        original_price = attrs.get("original_price", getattr(self.instance, "original_price", None))
        offer_price = attrs.get("offer_price", getattr(self.instance, "offer_price", None))

        if original_price is not None and original_price < 0:
            raise serializers.ValidationError({"original_price": "Price cannot be negative."})
        if offer_price is not None and offer_price < 0:
            raise serializers.ValidationError({"offer_price": "Price cannot be negative."})

        return attrs
