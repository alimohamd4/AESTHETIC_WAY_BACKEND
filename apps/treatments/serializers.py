from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.clinics.models import Clinic
from apps.practitioners.models import Practitioner
from apps.treatments.models import Category, Treatment


class PublicCategorySerializer(serializers.ModelSerializer):
    """Public serializer for treatment categories."""

    class Meta:
        model = Category
        fields = [
            "id",
            "name_en",
            "name_ar",
            "slug",
            "icon",
            "display_order",
        ]
        read_only_fields = fields


class PublicTreatmentClinicSummarySerializer(serializers.ModelSerializer):
    """Lightweight clinic summary for treatment responses."""

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


class PublicTreatmentPractitionerSummarySerializer(serializers.ModelSerializer):
    """Public practitioner summary performing a treatment."""

    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = Practitioner
        fields = [
            "id",
            "name_en",
            "name_ar",
            "title_en",
            "title_ar",
            "type",
            "avatar_url",
        ]
        read_only_fields = fields


class PublicTreatmentListSerializer(serializers.ModelSerializer):
    """Public listing serializer for treatments."""

    clinic = PublicTreatmentClinicSummarySerializer(read_only=True)
    category = PublicCategorySerializer(read_only=True)

    class Meta:
        model = Treatment
        fields = [
            "id",
            "name_en",
            "name_ar",
            "description_en",
            "description_ar",
            "price",
            "clinic",
            "category",
        ]
        read_only_fields = fields


class PublicTreatmentDetailSerializer(serializers.ModelSerializer):
    """Public detail serializer for a single treatment."""

    clinic = PublicTreatmentClinicSummarySerializer(read_only=True)
    category = PublicCategorySerializer(read_only=True)
    practitioners = serializers.SerializerMethodField()

    class Meta:
        model = Treatment
        fields = [
            "id",
            "name_en",
            "name_ar",
            "description_en",
            "description_ar",
            "price",
            "clinic",
            "category",
            "practitioners",
        ]
        read_only_fields = fields

    @extend_schema_field(PublicTreatmentPractitionerSummarySerializer(many=True))
    def get_practitioners(self, obj):
        # Only return active practitioners belonging to the treatment's clinic
        active_practitioners = obj.practitioners.filter(
            status="active",
            deleted_at__isnull=True,
            clinic_id=obj.clinic_id,
        ).order_by("display_order", "name_en")
        return PublicTreatmentPractitionerSummarySerializer(
            active_practitioners, many=True
        ).data
