from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.clinics.models import Clinic
from apps.practitioners.models import Practitioner
from apps.treatments.models import Treatment


class PublicPractitionerClinicSummarySerializer(serializers.ModelSerializer):
    """Public clinic summary for practitioner responses."""

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


class PublicPractitionerTreatmentSummarySerializer(serializers.ModelSerializer):
    """Treatments performed by a practitioner."""

    class Meta:
        model = Treatment
        fields = [
            "id",
            "name_en",
            "name_ar",
            "price",
        ]
        read_only_fields = fields


class PublicPractitionerListSerializer(serializers.ModelSerializer):
    """
    Public listing serializer for medical practitioners.
    STRICT SECURITY EXCLUSION:
    - license_number, license_authority
    - internal status, deleted_at
    - internal moderation info
    """

    clinic = PublicPractitionerClinicSummarySerializer(read_only=True)
    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = Practitioner
        fields = [
            "id",
            "clinic",
            "type",
            "name_en",
            "name_ar",
            "title_en",
            "title_ar",
            "bio_en",
            "bio_ar",
            "speciality_en",
            "speciality_ar",
            "avatar_url",
            "display_order",
        ]
        read_only_fields = fields


class PublicPractitionerDetailSerializer(serializers.ModelSerializer):
    """
    Public detail serializer for a practitioner profile.
    Includes clinic public information and treatments performed.
    """

    clinic = PublicPractitionerClinicSummarySerializer(read_only=True)
    avatar_url = serializers.CharField(read_only=True)
    treatments = serializers.SerializerMethodField()

    class Meta:
        model = Practitioner
        fields = [
            "id",
            "clinic",
            "type",
            "name_en",
            "name_ar",
            "title_en",
            "title_ar",
            "bio_en",
            "bio_ar",
            "speciality_en",
            "speciality_ar",
            "avatar_url",
            "display_order",
            "treatments",
        ]
        read_only_fields = fields

    @extend_schema_field(PublicPractitionerTreatmentSummarySerializer(many=True))
    def get_treatments(self, obj):
        active_treatments = obj.treatments.filter(
            is_active=True,
            status="active",
            deleted_at__isnull=True,
            clinic_id=obj.clinic_id,
        ).order_by("name_en")
        return PublicPractitionerTreatmentSummarySerializer(
            active_treatments, many=True
        ).data
