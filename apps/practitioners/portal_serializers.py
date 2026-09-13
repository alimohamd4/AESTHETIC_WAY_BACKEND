from rest_framework import serializers

from apps.media.models import MediaAsset
from apps.practitioners.models import (
    Practitioner,
    PractitionerStatus,
    PractitionerType,
)


class ClinicPractitionerPortalSerializer(serializers.ModelSerializer):
    """
    Serializer for managing medical practitioners within the clinic portal.
    Clinic ownership is derived from the authenticated session and is read-only.
    """

    avatar_url = serializers.CharField(read_only=True)
    media_asset = serializers.PrimaryKeyRelatedField(
        queryset=MediaAsset.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Practitioner
        fields = [
            "id",
            "name_en",
            "name_ar",
            "title_en",
            "title_ar",
            "bio_en",
            "bio_ar",
            "speciality_en",
            "speciality_ar",
            "type",
            "license_number",
            "license_authority",
            "avatar",
            "media_asset",
            "avatar_url",
            "status",
            "display_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "avatar_url", "created_at", "updated_at"]

    def validate_type(self, value):
        if value not in PractitionerType.values:
            raise serializers.ValidationError(
                f"Invalid practitioner type. Must be one of: {PractitionerType.values}"
            )
        return value

    def validate_status(self, value):
        if value not in PractitionerStatus.values:
            raise serializers.ValidationError(
                f"Invalid practitioner status. Must be one of: {PractitionerStatus.values}"
            )
        return value
