"""
AESTHETIC WAY Backend - Admin Portal Serializers (Phase 16)
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.admin_portal.models import AdminAuditLog
from apps.app_config.models import PlatformSetting
from apps.clinics.models import Clinic, ClinicBranch, ClinicStatus, SubscriptionTier
from apps.leads.models import Lead

# =====================================================================
# Backward Compatibility Serializers
# =====================================================================

class AdminClinicSerializer(serializers.ModelSerializer):
    """Legacy serializer retained for backward compatibility."""
    class Meta:
        model = Clinic
        fields = [
            "id", "name_en", "name_ar", "city", "status",
            "subscription_tier", "license_number", "is_active", "created_at"
        ]
        read_only_fields = ["id", "is_active", "created_at"]


class ClinicStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "active", "suspended", "rejected"])
    moderation_notes = serializers.CharField(required=False, allow_blank=True)


class ClinicSubscriptionUpdateSerializer(serializers.Serializer):
    subscription_tier = serializers.ChoiceField(choices=["basic", "featured", "vip"])


class PlatformSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformSetting
        fields = ["key", "value", "updated_at"]


class ContentModerationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "active", "suspended", "rejected"])


# =====================================================================
# Phase 16 Super Admin Serializers
# =====================================================================

class AdminDashboardSerializer(serializers.Serializer):
    total_clinics = serializers.IntegerField()
    active_clinics = serializers.IntegerField()
    suspended_clinics = serializers.IntegerField()
    pending_clinics = serializers.IntegerField()
    total_patients = serializers.IntegerField()
    total_practitioners = serializers.IntegerField()
    total_treatments = serializers.IntegerField()
    total_offers = serializers.IntegerField()
    total_products = serializers.IntegerField()
    total_articles = serializers.IntegerField()
    total_leads = serializers.IntegerField()
    completed_leads = serializers.IntegerField()
    scheduled_leads = serializers.IntegerField()
    leads_by_status = serializers.DictField(child=serializers.IntegerField())
    conversion_percentage = serializers.FloatField()
    total_referrals = serializers.IntegerField()
    total_redeemed_referral_codes = serializers.IntegerField()
    total_analytics_events = serializers.IntegerField()
    active_subscription_tiers = serializers.DictField(child=serializers.IntegerField())
    featured_clinics = serializers.IntegerField()


class AdminClinicBranchSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicBranch
        fields = [
            "id", "name_en", "name_ar", "address_en", "city", "phone",
            "is_main_branch", "is_active"
        ]


class AdminClinicListSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    branches_count = serializers.IntegerField(read_only=True, default=0)
    practitioners_count = serializers.IntegerField(read_only=True, default=0)
    treatments_count = serializers.IntegerField(read_only=True, default=0)
    offers_count = serializers.IntegerField(read_only=True, default=0)
    products_count = serializers.IntegerField(read_only=True, default=0)
    articles_count = serializers.IntegerField(read_only=True, default=0)
    leads_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Clinic
        fields = [
            "id", "name_en", "name_ar", "slug", "city", "emirate",
            "status", "subscription_tier", "is_active", "is_featured",
            "display_order", "license_number", "license_authority",
            "phone", "whatsapp", "email", "logo", "cover_image",
            "branches_count", "practitioners_count", "treatments_count",
            "offers_count", "products_count", "articles_count", "leads_count",
            "created_at", "updated_at"
        ]
        read_only_fields = fields


class AdminClinicDetailSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    branches = AdminClinicBranchSummarySerializer(many=True, read_only=True)
    practitioners_count = serializers.IntegerField(read_only=True, default=0)
    treatments_count = serializers.IntegerField(read_only=True, default=0)
    offers_count = serializers.IntegerField(read_only=True, default=0)
    products_count = serializers.IntegerField(read_only=True, default=0)
    articles_count = serializers.IntegerField(read_only=True, default=0)
    leads_count = serializers.IntegerField(read_only=True, default=0)
    leads_by_status = serializers.DictField(read_only=True, default=dict)
    moderated_by_id = serializers.UUIDField(source="moderated_by.id", read_only=True, default=None)

    class Meta:
        model = Clinic
        fields = [
            "id", "name_en", "name_ar", "slug", "description_en", "description_ar",
            "phone", "whatsapp", "email", "website",
            "address_en", "address_ar", "city", "emirate",
            "latitude", "longitude", "google_place_id", "google_maps_url",
            "logo", "cover_image", "google_rating",
            "status", "subscription_tier", "is_active", "is_featured", "display_order",
            "license_number", "license_authority",
            "moderation_notes", "moderated_at", "moderated_by_id",
            "branches",
            "practitioners_count", "treatments_count", "offers_count",
            "products_count", "articles_count", "leads_count",
            "leads_by_status",
            "created_at", "updated_at"
        ]
        read_only_fields = fields


class AdminClinicActionSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    moderation_notes = serializers.CharField(required=False, allow_blank=True, default="")


class AdminClinicUpdateSerializer(serializers.ModelSerializer):
    subscription_tier = serializers.ChoiceField(
        choices=SubscriptionTier.choices, required=False
    )
    status = serializers.ChoiceField(
        choices=ClinicStatus.choices, required=False
    )
    is_featured = serializers.BooleanField(required=False)
    display_order = serializers.IntegerField(required=False, min_value=0)
    license_number = serializers.CharField(required=False, allow_blank=True)
    license_authority = serializers.CharField(required=False, allow_blank=True)
    moderation_notes = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Clinic
        fields = [
            "subscription_tier", "status", "is_featured", "display_order",
            "license_number", "license_authority", "moderation_notes"
        ]


class AdminLeadClinicSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Clinic
        fields = ["id", "name_en", "name_ar", "slug", "city", "phone"]


class AdminLeadEntitySummarySerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name_en = serializers.CharField(read_only=True, default="")
    title_en = serializers.CharField(read_only=True, default="")


class AdminLeadSerializer(serializers.ModelSerializer):
    clinic = AdminLeadClinicSummarySerializer(read_only=True)
    branch = serializers.SerializerMethodField()
    practitioner = serializers.SerializerMethodField()
    treatment = serializers.SerializerMethodField()
    offer = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            "id", "reference_code", "status", "lead_type", "service_name",
            "clinic", "branch", "practitioner", "treatment", "offer", "product",
            "patient_name", "patient_phone", "patient_email",
            "preferred_time_window", "notes", "consent_accepted",
            "created_at", "updated_at"
        ]
        read_only_fields = fields

    @extend_schema_field(AdminLeadEntitySummarySerializer)
    def get_branch(self, obj):
        if obj.branch:
            return {"id": obj.branch.id, "name_en": obj.branch.name_en}
        return None

    @extend_schema_field(AdminLeadEntitySummarySerializer)
    def get_practitioner(self, obj):
        if obj.practitioner:
            return {"id": obj.practitioner.id, "name_en": obj.practitioner.name_en}
        return None

    @extend_schema_field(AdminLeadEntitySummarySerializer)
    def get_treatment(self, obj):
        if obj.treatment:
            return {"id": obj.treatment.id, "name_en": obj.treatment.name_en}
        return None

    @extend_schema_field(AdminLeadEntitySummarySerializer)
    def get_offer(self, obj):
        if obj.offer:
            return {"id": obj.offer.id, "title_en": obj.offer.title_en}
        return None

    @extend_schema_field(AdminLeadEntitySummarySerializer)
    def get_product(self, obj):
        if obj.product:
            return {"id": obj.product.id, "name_en": obj.product.name_en}
        return None


class AdminModerationItemSerializer(serializers.Serializer):
    content_type = serializers.CharField()
    id = serializers.UUIDField()
    title = serializers.CharField()
    status = serializers.CharField()
    clinic_id = serializers.UUIDField(allow_null=True)
    clinic_name = serializers.CharField(allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class AdminModerationActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["approve", "reject", "suspend", "hide", "restore"],
        required=False
    )
    status = serializers.ChoiceField(
        choices=["pending", "active", "suspended", "rejected"],
        required=False
    )
    moderation_notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("action") and not attrs.get("status"):
            raise serializers.ValidationError("Either 'action' or 'status' must be provided.")
        return attrs

    def get_target_status(self):
        validated_data = self.validated_data
        action = validated_data.get("action")
        if action:
            action_map = {
                "approve": "active",
                "restore": "active",
                "reject": "rejected",
                "suspend": "suspended",
                "hide": "suspended",
            }
            return action_map.get(action)
        return validated_data.get("status")


class AdminAuditLogSerializer(serializers.ModelSerializer):
    admin_id = serializers.UUIDField(source="admin.id", read_only=True, default=None)
    admin_phone = serializers.CharField(source="admin.phone", read_only=True, default="")
    admin_name = serializers.CharField(source="admin.full_name", read_only=True, default="")

    class Meta:
        model = AdminAuditLog
        fields = [
            "id", "admin_id", "admin_phone", "admin_name",
            "action_type", "entity_type", "entity_id", "details",
            "created_at"
        ]
        read_only_fields = fields


ALLOWED_SETTING_KEYS = {
    "support_phone",
    "support_whatsapp",
    "support_phone_display",
    "maintenance_mode",
    "referral_milestone_20_points",
    "referral_milestone_35_points",
    "referral_milestone_50_points",
    "referral_collect_threshold",
    "app_min_version_ios",
    "app_min_version_android",
    "terms_version",
}


class AdminPlatformSettingUpdateSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=100)
    value = serializers.JSONField()

    def validate_key(self, value):
        if value not in ALLOWED_SETTING_KEYS:
            raise serializers.ValidationError(
                f"Setting key '{value}' is not configurable or forbidden."
            )
        return value


class AdminPlatformAnalyticsSerializer(serializers.Serializer):
    date_from = serializers.DateField(allow_null=True)
    date_to = serializers.DateField(allow_null=True)
    total_events = serializers.IntegerField()
    app_opens = serializers.IntegerField()
    clinic_views = serializers.IntegerField()
    whatsapp_taps = serializers.IntegerField()
    call_taps = serializers.IntegerField()
    maps_taps = serializers.IntegerField()
    lead_submissions = serializers.IntegerField()
    conversion_metrics = serializers.DictField()
    daily_trends = serializers.ListField(child=serializers.DictField())
    clinic_engagement = serializers.ListField(child=serializers.DictField())
