from datetime import timedelta

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, views
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.analytics.models import AnalyticsEvent, EventType
from apps.analytics.serializers import (
    AnalyticsEventIngestionSerializer,
    ClinicAnalyticsResponseSerializer,
)
from apps.leads.models import Lead


class EventIngestionAPIView(generics.CreateAPIView):
    """
    Public endpoint for tracking telemetry.
    We rely on DRF's built-in throttle_classes in production settings
    to prevent abuse (e.g., 60/minute).
    """
    permission_classes = [AllowAny]
    serializer_class = AnalyticsEventIngestionSerializer

    def perform_create(self, serializer):
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(user=user)


class ClinicAnalyticsAPIView(views.APIView):
    """
    Clinic dashboard analytics. Aggregates data server-side.
    Requires staff role.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ClinicAnalyticsResponseSerializer})
    def get(self, request, *args, **kwargs):
        if not request.user.is_clinic_user:
            raise PermissionDenied("Only clinic staff can access this endpoint.")

        clinic_user = request.user.clinic_memberships.filter(is_active=True).first()
        if not clinic_user:
            raise PermissionDenied("No active clinic assignment found.")

        clinic = clinic_user.clinic

        # Simple 30 day timeframe filter
        timeframe = timezone.now() - timedelta(days=30)

        # Aggregate Events
        events = AnalyticsEvent.objects.filter(clinic=clinic, timestamp__gte=timeframe)

        profile_views = events.filter(event_type=EventType.CLINIC_VIEW).count()
        whatsapp_taps = events.filter(event_type=EventType.WHATSAPP_TAP).count()
        call_taps = events.filter(event_type=EventType.CALL_TAP).count()
        maps_taps = events.filter(event_type=EventType.MAPS_TAP).count()

        # Aggregate Leads
        leads = Lead.objects.filter(clinic=clinic, created_at__gte=timeframe)
        total_leads = leads.count()

        contacted_count = leads.filter(status__in=["contacted", "closed"]).count()
        contacted_conversion_percentage = 0.0
        if total_leads > 0:
            contacted_conversion_percentage = (contacted_count / total_leads) * 100.0

        # Referral conversions (mock: global total successful invites related to this clinic's patients?
        # The prompt says "referral conversions". Since Referral invites don't have a clinic FK,
        # we might just return 0 or calculate the number of discount codes redeemed here).
        # Let's calculate the number of discount codes redeemed at this clinic.
        from apps.referrals.models import ReferralDiscountCode
        referral_conversions = ReferralDiscountCode.objects.filter(
            redeemed_clinic=clinic, redeemed_at__gte=timeframe
        ).count()

        serializer = ClinicAnalyticsResponseSerializer({
            "profile_views": profile_views,
            "whatsapp_taps": whatsapp_taps,
            "call_taps": call_taps,
            "maps_taps": maps_taps,
            "total_leads": total_leads,
            "contacted_conversion_percentage": round(contacted_conversion_percentage, 2),
            "referral_conversions": referral_conversions
        })

        return Response(serializer.data)
