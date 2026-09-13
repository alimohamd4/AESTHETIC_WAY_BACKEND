from rest_framework import serializers

from apps.referrals.models import ReferralDiscountCode


class ReferralDiscountCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReferralDiscountCode
        fields = ["id", "code", "status", "redeemed_at", "created_at", "expires_at"]
        read_only_fields = fields

class PatientStatusSerializer(serializers.Serializer):
    referral_code = serializers.CharField(read_only=True)
    successful_invites_count = serializers.IntegerField(read_only=True)
    current_points = serializers.IntegerField(read_only=True)
    points_to_collect = serializers.IntegerField(read_only=True, default=500)
    can_collect_code = serializers.BooleanField(read_only=True)
    points_expire = serializers.BooleanField(read_only=True, default=False)
    milestones = serializers.DictField(read_only=True)
    total_successful_invites = serializers.IntegerField(read_only=True)
    discount_codes = ReferralDiscountCodeSerializer(many=True, read_only=True)

class VerifyCodeRequestSerializer(serializers.Serializer):
    code = serializers.CharField(required=True)

class VerifyCodeResponseSerializer(serializers.Serializer):
    is_valid = serializers.BooleanField()
    message = serializers.CharField()
    code = serializers.CharField()
    status = serializers.CharField()
    expires_at = serializers.DateTimeField()
