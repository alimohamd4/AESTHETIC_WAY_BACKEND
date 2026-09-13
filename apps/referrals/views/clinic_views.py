from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.referrals.models import DiscountCodeStatus, ReferralDiscountCode
from apps.referrals.serializers import VerifyCodeRequestSerializer, VerifyCodeResponseSerializer


class VerifyDiscountCodeAPIView(APIView):
    """
    Clinic endpoint to verify a discount code.
    Returns the status without mutating the code.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=VerifyCodeRequestSerializer,
        responses={
            200: VerifyCodeResponseSerializer,
            404: OpenApiResponse(description="Invalid discount code."),
        },
    )
    def post(self, request, *args, **kwargs):
        if not request.user.is_clinic_user and request.user.role != UserRole.SUPER_ADMIN:
            raise PermissionDenied("Only clinic staff can verify codes.")

        req_serializer = VerifyCodeRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        code_str = req_serializer.validated_data["code"]

        try:
            code_obj = ReferralDiscountCode.objects.get(code=code_str)
        except ReferralDiscountCode.DoesNotExist:
            return Response({"detail": "Invalid discount code."}, status=status.HTTP_404_NOT_FOUND)

        is_valid = True
        message = "Code is valid and ready for redemption."

        if code_obj.status == DiscountCodeStatus.USED:
            is_valid = False
            message = "This code has already been redeemed."
        elif code_obj.status == DiscountCodeStatus.EXPIRED or timezone.now() > code_obj.expires_at:
            is_valid = False
            message = "This code has expired."

        res_serializer = VerifyCodeResponseSerializer({
            "is_valid": is_valid,
            "message": message,
            "code": code_obj.code,
            "status": code_obj.status,
            "expires_at": code_obj.expires_at
        })

        return Response(res_serializer.data, status=status.HTTP_200_OK)


class RedeemDiscountCodeAPIView(APIView):
    """
    Clinic endpoint to redeem a discount code.
    Ensures race conditions are prevented.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=VerifyCodeRequestSerializer,
        responses={
            200: OpenApiResponse(description="Discount code successfully redeemed"),
            400: OpenApiResponse(description="Code already redeemed or expired"),
            404: OpenApiResponse(description="Invalid discount code."),
        },
    )
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        if not request.user.is_clinic_user:
            raise PermissionDenied("Only clinic staff can redeem codes.")

        req_serializer = VerifyCodeRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        code_str = req_serializer.validated_data["code"]

        # Lock the code row
        try:
            code_obj = ReferralDiscountCode.objects.select_for_update().get(code=code_str)
        except ReferralDiscountCode.DoesNotExist:
            return Response({"detail": "Invalid discount code."}, status=status.HTTP_404_NOT_FOUND)

        if code_obj.status == DiscountCodeStatus.USED:
            return Response({"detail": "This code has already been redeemed."}, status=status.HTTP_400_BAD_REQUEST)

        if code_obj.status == DiscountCodeStatus.EXPIRED or timezone.now() > code_obj.expires_at:
            return Response({"detail": "This code has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # Redeem the code
        clinic_user = request.user.clinic_memberships.filter(is_active=True).first()
        if not clinic_user:
            raise PermissionDenied("You are not actively assigned to a clinic.")

        code_obj.status = DiscountCodeStatus.USED
        code_obj.redeemed_at = timezone.now()
        code_obj.redeemed_clinic = clinic_user.clinic
        code_obj.save(update_fields=["status", "redeemed_at", "redeemed_clinic"])

        from apps.admin_portal.models import AdminActionType, AdminAuditLog
        AdminAuditLog.objects.create(
            admin=request.user,
            action_type=AdminActionType.REDEEM_DISCOUNT,
            entity_type="ReferralDiscountCode",
            entity_id=code_obj.id,
            details={"code": code_obj.code, "clinic_id": str(clinic_user.clinic.id)}
        )

        # --- Notify the patient their code was redeemed (fire-and-forget) ---
        from apps.notifications.models import NotificationType
        from apps.notifications.service import NotificationService

        NotificationService.send_async(
            recipient=code_obj.patient,
            notification_type=NotificationType.DISCOUNT_REDEEMED,
            payload={"code": code_obj.code, "clinic": code_obj.redeemed_clinic.name_en},
        )

        return Response({
            "success": True,
            "message": "Successfully applied 15% discount.",
            "code": code_obj.code,
            "redeemed_clinic": code_obj.redeemed_clinic.name_en
        }, status=status.HTTP_200_OK)

