from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.clinics.models import Clinic, ClinicBranch
from apps.practitioners.models import Practitioner
from apps.treatments.models import Category, Treatment


class PublicClinicBranchSerializer(serializers.ModelSerializer):
    """Public serializer for clinic branch locations."""

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
        ]
        read_only_fields = fields


class PublicClinicListSerializer(serializers.ModelSerializer):
    """
    Public listing serializer for clinics.
    STRICT SECURITY EXCLUSION:
    - subscription_tier (used internally for ranking only)
    - license_number, license_authority
    - moderation_notes, moderated_by, moderated_at
    - internal status, deleted_at
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
        read_only_fields = fields


class PublicClinicCategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name_en", "name_ar", "slug"]
        read_only_fields = fields


class PublicClinicTreatmentSummarySerializer(serializers.ModelSerializer):
    category = PublicClinicCategorySummarySerializer(read_only=True)

    class Meta:
        model = Treatment
        fields = [
            "id",
            "name_en",
            "name_ar",
            "description_en",
            "description_ar",
            "price",
            "category",
        ]
        read_only_fields = fields


class PublicClinicPractitionerSummarySerializer(serializers.ModelSerializer):
    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = Practitioner
        fields = [
            "id",
            "name_en",
            "name_ar",
            "title_en",
            "title_ar",
            "speciality_en",
            "speciality_ar",
            "type",
            "avatar_url",
        ]
        read_only_fields = fields


class PublicClinicDetailSerializer(serializers.ModelSerializer):
    """
    Public detail serializer for clinic profile.
    Includes branches, active practitioners, and active treatments.
    """

    branches = serializers.SerializerMethodField()
    practitioners = serializers.SerializerMethodField()
    treatments = serializers.SerializerMethodField()

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
            "branches",
            "practitioners",
            "treatments",
        ]
        read_only_fields = fields

    @extend_schema_field(PublicClinicBranchSerializer(many=True))
    def get_branches(self, obj):
        active_branches = obj.branches.filter(
            is_active=True,
            deleted_at__isnull=True,
        ).order_by("-is_main_branch", "name_en")
        return PublicClinicBranchSerializer(active_branches, many=True).data

    @extend_schema_field(PublicClinicPractitionerSummarySerializer(many=True))
    def get_practitioners(self, obj):
        active_practitioners = obj.practitioners.filter(
            status="active",
            deleted_at__isnull=True,
        ).order_by("display_order", "name_en")
        return PublicClinicPractitionerSummarySerializer(
            active_practitioners, many=True
        ).data

    @extend_schema_field(PublicClinicTreatmentSummarySerializer(many=True))
    def get_treatments(self, obj):
        active_treatments = obj.treatments.filter(
            is_active=True,
            status="active",
            deleted_at__isnull=True,
            category__is_active=True,
        ).select_related("category").order_by("name_en")
        return PublicClinicTreatmentSummarySerializer(
            active_treatments, many=True
        ).data
