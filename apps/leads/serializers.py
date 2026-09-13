from django.utils import timezone
from rest_framework import serializers

from apps.clinics.models import Clinic, ClinicBranch, ClinicStatus
from apps.leads.models import Lead, LeadNote, LeadStatus, LeadStatusHistory
from apps.offers.models import Offer
from apps.practitioners.models import Practitioner
from apps.products.models import Product
from apps.treatments.models import Treatment


class LeadNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)

    class Meta:
        model = LeadNote
        fields = ["id", "author_name", "note", "created_at"]
        read_only_fields = ["id", "author_name", "created_at"]


class LeadStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True)

    class Meta:
        model = LeadStatusHistory
        fields = ["id", "status", "changed_by_name", "created_at"]
        read_only_fields = ["id", "status", "changed_by_name", "created_at"]


# --- Patient-safe Summary Serializers ----------------------------------------

class PatientClinicSummarySerializer(serializers.ModelSerializer):
    """Safe clinic contact and location summary for patient view."""
    logo_url = serializers.CharField(read_only=True)

    class Meta:
        model = Clinic
        fields = [
            "id", "name_en", "name_ar", "slug", "phone", "whatsapp",
            "address_en", "address_ar", "city", "logo_url"
        ]


class PatientBranchSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicBranch
        fields = ["id", "name_en", "name_ar", "address_en", "address_ar", "city"]


class PatientPractitionerSummarySerializer(serializers.ModelSerializer):
    profile_image_url = serializers.CharField(read_only=True)

    class Meta:
        model = Practitioner
        fields = ["id", "name_en", "name_ar", "type", "profile_image_url"]


class PatientTreatmentSummarySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name_en", read_only=True)

    class Meta:
        model = Treatment
        fields = ["id", "name_en", "name_ar", "category_name", "price"]


class PatientOfferSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = ["id", "title_en", "title_ar", "original_price", "offer_price"]


class PatientProductSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name_en", "name_ar", "price"]


# --- Patient Lead List & Detail Serializer -----------------------------------

class PatientLeadSerializer(serializers.ModelSerializer):
    """
    Serializer for the patient app.
    Provides contact info and entity summaries while strictly omitting internal clinic notes,
    status history, moderation, and regulatory fields.
    """
    clinic_name = serializers.CharField(source="clinic.name_en", read_only=True)
    clinic_summary = PatientClinicSummarySerializer(source="clinic", read_only=True)
    branch_summary = PatientBranchSummarySerializer(source="branch", read_only=True)
    practitioner_summary = PatientPractitionerSummarySerializer(source="practitioner", read_only=True)
    treatment_summary = PatientTreatmentSummarySerializer(source="treatment", read_only=True)
    offer_summary = PatientOfferSummarySerializer(source="offer", read_only=True)
    product_summary = PatientProductSummarySerializer(source="product", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "reference_code", "status", "lead_type", "service_name",
            "patient_name", "patient_phone", "patient_email",
            "preferred_time_window", "notes", "created_at", "updated_at",
            "clinic", "clinic_name", "clinic_summary",
            "branch", "branch_summary",
            "practitioner", "practitioner_summary",
            "treatment", "treatment_summary",
            "offer", "offer_summary",
            "product", "product_summary",
        ]
        read_only_fields = [
            "id", "reference_code", "status", "created_at", "updated_at",
            "clinic_name", "clinic_summary", "branch_summary", "practitioner_summary",
            "treatment_summary", "offer_summary", "product_summary"
        ]


class PatientLeadCreateSerializer(serializers.ModelSerializer):
    """
    Serializer used specifically for lead creation by patients.
    Validates consent_accepted and rigorously checks cross-clinic entity binding,
    entity activation status, offer validity, and treatment-practitioner assignments.
    """
    patient_name = serializers.CharField(max_length=200, required=False)
    patient_phone = serializers.CharField(max_length=20, required=False)
    patient_email = serializers.EmailField(required=False, allow_blank=True)
    treatment = serializers.PrimaryKeyRelatedField(
        queryset=Treatment.objects.filter(is_active=True, deleted_at__isnull=True),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Lead
        fields = [
            "clinic", "branch", "practitioner", "treatment", "offer", "product",
            "lead_type", "service_name", "patient_name", "patient_phone",
            "patient_email", "preferred_time_window", "notes", "consent_accepted"
        ]

    def validate_consent_accepted(self, value):
        if not value:
            raise serializers.ValidationError("Consent must be accepted.")
        return value

    def validate(self, attrs):
        clinic = attrs.get("clinic")
        if not clinic:
            raise serializers.ValidationError({"clinic": "Clinic is required."})

        # 1. Clinic must not be suspended, rejected, or soft-deleted
        if clinic.status in (ClinicStatus.SUSPENDED, ClinicStatus.REJECTED) or clinic.deleted_at is not None:
            raise serializers.ValidationError({"clinic": "Clinic is not active or has been deleted."})

        # 2. Branch cross-clinic validation
        branch = attrs.get("branch")
        if branch:
            if branch.clinic_id != clinic.id:
                raise serializers.ValidationError({"branch": "Branch does not belong to the selected clinic."})
            if not branch.is_active or branch.deleted_at is not None:
                raise serializers.ValidationError({"branch": "Branch is not active or has been deleted."})

        # 3. Practitioner cross-clinic validation
        practitioner = attrs.get("practitioner")
        if practitioner:
            if practitioner.clinic_id != clinic.id:
                raise serializers.ValidationError({"practitioner": "Practitioner does not belong to the selected clinic."})
            if practitioner.status != "active" or practitioner.deleted_at is not None:
                raise serializers.ValidationError({"practitioner": "Practitioner is not active or has been deleted."})

        # 4. Treatment cross-clinic and practitioner assignment validation
        treatment = attrs.get("treatment")
        if treatment:
            if treatment.clinic_id != clinic.id:
                raise serializers.ValidationError({"treatment": "Treatment does not belong to the selected clinic."})
            if not treatment.is_active or treatment.deleted_at is not None:
                raise serializers.ValidationError({"treatment": "Treatment is not active or has been deleted."})
            if practitioner:
                if not treatment.practitioners.filter(id=practitioner.id, status="active", deleted_at__isnull=True).exists():
                    raise serializers.ValidationError({"practitioner": "Practitioner is not assigned to the selected treatment."})
            if not attrs.get("service_name"):
                attrs["service_name"] = treatment.name_en

        # 5. Offer cross-clinic and date window validation
        offer = attrs.get("offer")
        if offer:
            if offer.clinic_id != clinic.id:
                raise serializers.ValidationError({"offer": "Offer does not belong to the selected clinic."})
            if not offer.is_active or offer.deleted_at is not None:
                raise serializers.ValidationError({"offer": "Offer is not active or has been deleted."})
            now = timezone.now()
            if offer.starts_at > now or offer.ends_at < now:
                raise serializers.ValidationError({"offer": "Offer is expired or not yet active."})

        # 6. Product cross-clinic validation
        product = attrs.get("product")
        if product:
            if product.clinic_id != clinic.id:
                raise serializers.ValidationError({"product": "Product does not belong to the selected clinic."})
            if not product.is_active or product.deleted_at is not None:
                raise serializers.ValidationError({"product": "Product is not active or has been deleted."})

        # 7. Patient details derivation
        request = self.context.get("request")
        user = request.user if request and request.user.is_authenticated else None

        patient_name = attrs.get("patient_name")
        if not patient_name:
            if user and user.full_name:
                attrs["patient_name"] = user.full_name
            else:
                raise serializers.ValidationError({"patient_name": "Patient name is required."})

        patient_phone = attrs.get("patient_phone")
        if not patient_phone:
            if user and user.phone:
                attrs["patient_phone"] = user.phone
            else:
                raise serializers.ValidationError({"patient_phone": "Patient phone is required."})

        patient_email = attrs.get("patient_email")
        if not patient_email and user and user.email:
            attrs["patient_email"] = user.email

        return attrs


class ClinicLeadSerializer(serializers.ModelSerializer):
    """
    Serializer for the clinic portal.
    Includes internal notes and status history.
    """
    internal_notes = LeadNoteSerializer(many=True, read_only=True)
    status_history = LeadStatusHistorySerializer(many=True, read_only=True)
    patient_user_id = serializers.PrimaryKeyRelatedField(source="patient", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "reference_code", "patient_user_id", "clinic", "branch",
            "practitioner", "treatment", "offer", "product", "lead_type", "service_name",
            "patient_name", "patient_phone", "patient_email",
            "preferred_time_window", "notes", "status", "internal_notes",
            "status_history", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "reference_code", "created_at", "updated_at", "clinic"]


class LeadStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = ["status"]

    def validate_status(self, value):
        if value not in [LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.CLOSED]:
            raise serializers.ValidationError("Invalid status.")
        return value
