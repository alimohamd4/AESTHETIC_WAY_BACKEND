from django.utils import timezone
from rest_framework import serializers

from apps.articles.models import Article, ContentStatus
from apps.clinics.portal_permissions import get_user_clinic
from apps.media.models import MediaAsset
from apps.practitioners.models import Practitioner


class ClinicArticlePortalSerializer(serializers.ModelSerializer):
    """
    Serializer for managing educational articles in the clinic portal.
    """

    cover_image_url = serializers.CharField(source="image_url", read_only=True)
    author_practitioner = serializers.PrimaryKeyRelatedField(
        queryset=Practitioner.objects.filter(deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    media_asset = serializers.PrimaryKeyRelatedField(
        queryset=MediaAsset.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Article
        fields = [
            "id",
            "title_en",
            "title_ar",
            "slug",
            "content_en",
            "content_ar",
            "author_practitioner",
            "cover_image",
            "media_asset",
            "cover_image_url",
            "is_published",
            "published_at",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "cover_image_url", "created_at", "updated_at"]

    def validate_status(self, value):
        if value not in ContentStatus.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {ContentStatus.values}"
            )
        return value

    def validate_author_practitioner(self, value):
        if not value:
            return value

        request = self.context.get("request")
        if not request:
            return value

        clinic = get_user_clinic(request.user)
        if value.clinic_id != clinic.id:
            raise serializers.ValidationError(
                "Author practitioner must belong to your clinic."
            )
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        clinic = get_user_clinic(request.user)
        validated_data["clinic"] = clinic

        # Set published_at if publishing for the first time
        if validated_data.get("is_published") and not validated_data.get("published_at"):
            validated_data["published_at"] = timezone.now()

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("is_published") and not instance.published_at and not validated_data.get("published_at"):
            validated_data["published_at"] = timezone.now()

        return super().update(instance, validated_data)
