from rest_framework import serializers
from apps.leads.models import Lead, LeadNote, LeadStatusHistory, LeadStatus

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

class PatientLeadSerializer(serializers.ModelSerializer):
    """
    Serializer for the patient app.
    Omits internal notes and history.
    """
    clinic_name = serializers.CharField(source="clinic.name_en", read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "reference_code", "clinic", "clinic_name", "branch", 
            "practitioner", "offer", "product", "lead_type", "service_name", 
            "patient_name", "patient_phone", "patient_email", 
            "preferred_time_window", "notes", "status", "created_at"
        ]
        read_only_fields = ["id", "reference_code", "status", "created_at", "clinic_name"]

class PatientLeadCreateSerializer(serializers.ModelSerializer):
    """
    Serializer used specifically for lead creation by patients.
    Validates consent_accepted.
    """
    class Meta:
        model = Lead
        fields = [
            "clinic", "branch", "practitioner", "offer", "product", 
            "lead_type", "service_name", "patient_name", "patient_phone", 
            "patient_email", "preferred_time_window", "notes", "consent_accepted"
        ]

    def validate_consent_accepted(self, value):
        if not value:
            raise serializers.ValidationError("Consent must be accepted.")
        return value

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
            "practitioner", "offer", "product", "lead_type", "service_name", 
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
