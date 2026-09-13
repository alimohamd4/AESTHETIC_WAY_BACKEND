from rest_framework import serializers

from apps.clinics.models import Clinic, ClinicBranch


class ClinicProfilePortalSerializer(serializers.ModelSerializer):
    """
    Clinic profile serializer for the clinic portal.
    Allows editing clinic contact, presentation, and maps fields.
    STRICTLY FORBIDS mutating:
    - subscription_tier
    - status
    - is_featured, display_order, google_rating
    - moderation_notes, moderated_by, moderated_at
    - license_number, license_authority
    - deleted_at
    """

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
            "google_place_id",
            "google_maps_url",
            "logo",
            "cover_image",
            "is_featured",
            "google_rating",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "is_featured",
            "google_rating",
            "created_at",
            "updated_at",
        ]


class ClinicBranchPortalSerializer(serializers.ModelSerializer):
    """
    Serializer for physical branch locations managed by the clinic.
    """

    class Meta:
        model = ClinicBranch
        fields = [
            "id",
            "name_en",
            "name_ar",
            "address_en",
            "address_ar",
            "city",
            "phone",
            "latitude",
            "longitude",
            "google_place_id",
            "google_maps_url",
            "is_main_branch",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
