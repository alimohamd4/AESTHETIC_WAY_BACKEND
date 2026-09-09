from rest_framework import serializers
from apps.analytics.models import AnalyticsEvent

class AnalyticsEventIngestionSerializer(serializers.ModelSerializer):
    """
    Serializer used by the mobile app to post events.
    Notice `timestamp` is omitted, it will be strictly server-generated.
    """
    class Meta:
        model = AnalyticsEvent
        fields = [
            "event_type",
            "anonymous_id",
            "clinic",
            "object_type",
            "object_id",
            "metadata"
        ]

class ClinicAnalyticsResponseSerializer(serializers.Serializer):
    """
    Response format for clinic analytics dashboard.
    """
    profile_views = serializers.IntegerField()
    whatsapp_taps = serializers.IntegerField()
    call_taps = serializers.IntegerField()
    maps_taps = serializers.IntegerField()
    total_leads = serializers.IntegerField()
    contacted_conversion_percentage = serializers.FloatField()
    referral_conversions = serializers.IntegerField()
