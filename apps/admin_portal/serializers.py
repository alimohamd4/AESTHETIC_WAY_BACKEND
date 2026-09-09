from rest_framework import serializers
from apps.clinics.models import Clinic
from apps.leads.models import Lead
from apps.offers.models import Offer
from apps.products.models import Product
from apps.articles.models import Article
from apps.app_config.models import PlatformSetting

class AdminClinicSerializer(serializers.ModelSerializer):
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
