from django.db import transaction
from rest_framework import serializers

from apps.clinics.portal_permissions import get_user_clinic
from apps.practitioners.models import Practitioner
from apps.treatments.models import (
    Category,
    PractitionerTreatment,
    Treatment,
    TreatmentStatus,
)


class ClinicTreatmentPortalSerializer(serializers.ModelSerializer):
    """
    Serializer for managing treatments in the clinic portal.
    Supports practitioner assignment with cross-clinic validation.
    """

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True)
    )
    category_name = serializers.CharField(source="category.name_en", read_only=True)
    practitioners = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Practitioner.objects.filter(deleted_at__isnull=True),
        required=False,
    )

    class Meta:
        model = Treatment
        fields = [
            "id",
            "category",
            "category_name",
            "name_en",
            "name_ar",
            "description_en",
            "description_ar",
            "price",
            "status",
            "is_active",
            "practitioners",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "category_name", "created_at", "updated_at"]

    def validate_status(self, value):
        if value not in TreatmentStatus.values:
            raise serializers.ValidationError(
                f"Invalid status. Must be one of: {TreatmentStatus.values}"
            )
        return value

    def validate_practitioners(self, practitioners):
        request = self.context.get("request")
        if not request:
            return practitioners

        clinic = get_user_clinic(request.user)
        for p in practitioners:
            if p.clinic_id != clinic.id:
                raise serializers.ValidationError(
                    f"Practitioner '{p.name_en}' belongs to another clinic and cannot be assigned."
                )
        return practitioners

    @transaction.atomic
    def create(self, validated_data):
        practitioners = validated_data.pop("practitioners", None)
        request = self.context.get("request")
        clinic = get_user_clinic(request.user)
        validated_data["clinic"] = clinic

        treatment = Treatment.objects.create(**validated_data)

        if practitioners is not None:
            for p in practitioners:
                PractitionerTreatment.objects.create(
                    treatment=treatment,
                    practitioner=p,
                )

        return treatment

    @transaction.atomic
    def update(self, instance, validated_data):
        practitioners = validated_data.pop("practitioners", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if practitioners is not None:
            # Re-sync practitioner treatments
            instance.practitioner_treatments.all().delete()
            for p in practitioners:
                PractitionerTreatment.objects.create(
                    treatment=instance,
                    practitioner=p,
                )

        return instance
