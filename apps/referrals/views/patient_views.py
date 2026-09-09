from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db import transaction
from django.db.models import Sum

from apps.accounts.models import PatientProfile
from apps.referrals.models import ReferralDiscountCode, ReferralPointsLedger, LedgerTransactionType
from apps.referrals.serializers import PatientStatusSerializer

class ReferralStatusAPIView(generics.RetrieveAPIView):
    """
    Returns the current referral status of the authenticated patient.
    """
    serializer_class = PatientStatusSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile = PatientProfile.objects.get(user=self.request.user)
        # We can dynamically pass the related codes
        codes = ReferralDiscountCode.objects.filter(patient=self.request.user)
        
        return {
            "current_points": profile.current_points,
            "total_successful_invites": profile.total_successful_invites,
            "discount_codes": codes
        }


class CollectCodeAPIView(APIView):
    """
    Collects a discount code by consuming 500 points.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        patient = request.user
        code = None

        with transaction.atomic():
            # Lock the profile to prevent concurrent point spending
            profile = PatientProfile.objects.select_for_update().get(user=patient)

            # Double check via ledger for maximum safety
            ledger_sum = ReferralPointsLedger.objects.filter(patient=patient).aggregate(Sum("points"))["points__sum"] or 0

            if ledger_sum < 500:
                return Response(
                    {"detail": "Insufficient points to collect a code. 500 points required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Deduct 500 points
            ReferralPointsLedger.objects.create(
                patient=patient,
                transaction_type=LedgerTransactionType.COLLECT_CODE,
                points=-500
            )

            # Update cache
            profile.current_points = ledger_sum - 500
            profile.save(update_fields=["current_points"])

            # Generate code (inside tx so points + code are always consistent)
            code = ReferralDiscountCode.objects.create(patient=patient)

        # --- Notification (fire-and-forget, outside the transaction) ---
        from apps.notifications.service import NotificationService
        from apps.notifications.models import NotificationType

        NotificationService.send_async(
            recipient=patient,
            notification_type=NotificationType.DISCOUNT_COLLECTED,
            payload={"code": code.code, "expires_at": str(code.expires_at)},
        )

        return Response({
            "success": True,
            "code": code.code,
            "expires_at": code.expires_at,
            "remaining_points": profile.current_points
        }, status=status.HTTP_201_CREATED)

