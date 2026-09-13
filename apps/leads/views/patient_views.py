import datetime
import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from apps.accounts.models import UserRole
from apps.leads.models import Lead, LeadStatus, LeadStatusHistory
from apps.leads.serializers import (
    PatientLeadCreateSerializer,
    PatientLeadSerializer,
)

logger = logging.getLogger(__name__)


class LeadCreationThrottle(UserRateThrottle):
    rate = "10/hour"


class AnonLeadCreationThrottle(AnonRateThrottle):
    rate = "10/hour"


class LeadCreateAPIView(generics.CreateAPIView):
    """
    Patient endpoint to submit a lead / booking inquiry.
    Guest leads are permitted but authenticated requests link to the patient user profile.
    """
    serializer_class = PatientLeadCreateSerializer
    permission_classes = [AllowAny]
    throttle_classes = [LeadCreationThrottle, AnonLeadCreationThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        clinic = serializer.validated_data.get("clinic")
        service_name = serializer.validated_data.get("service_name")
        patient_phone = serializer.validated_data.get("patient_phone")
        treatment = serializer.validated_data.get("treatment")

        # Duplication check: exact same clinic and service/treatment for the same phone within 24h
        cutoff = timezone.now() - datetime.timedelta(hours=24)
        dup_filter = Lead.objects.filter(
            clinic=clinic,
            patient_phone=patient_phone,
            created_at__gte=cutoff
        )
        if treatment:
            duplicate = dup_filter.filter(treatment=treatment).exists()
        else:
            duplicate = dup_filter.filter(service_name=service_name).exists()

        if duplicate:
            return Response(
                {"detail": "A request for this service at this clinic was already submitted recently."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Force server-side patient derivation (cannot be overridden by client)
        patient = request.user if request.user.is_authenticated else None

        lead = serializer.save(patient=patient, status=LeadStatus.NEW)

        # Write initial history log
        LeadStatusHistory.objects.create(
            lead=lead,
            status=LeadStatus.NEW,
            changed_by=patient
        )

        # --- Notifications (fire-and-forget, never blocks the response) ---
        try:
            from apps.notifications.models import NotificationType
            from apps.notifications.service import NotificationService

            # Notify clinic staff of the new lead
            clinic_staff = lead.clinic.clinic_users.filter(is_active=True).select_related("user").first()
            if clinic_staff and clinic_staff.user:
                NotificationService.send_async(
                    recipient=clinic_staff.user,
                    notification_type=NotificationType.NEW_LEAD_CLINIC,
                    payload={
                        "lead_id": str(lead.id),
                        "reference": lead.reference_code,
                        "patient_name": lead.patient_name
                    },
                )

            # Notify patient of their lead confirmation
            if patient:
                NotificationService.send_async(
                    recipient=patient,
                    notification_type=NotificationType.LEAD_CONFIRMATION_PATIENT,
                    payload={"lead_id": str(lead.id), "reference": lead.reference_code},
                )
        except Exception as exc:
            logger.warning("Failed to dispatch lead notification for %s: %s", lead.reference_code, exc)

        # --- Analytics event (fire-and-forget) ---
        try:
            from apps.analytics.models import AnalyticsEvent, EventType
            AnalyticsEvent.objects.create(
                event_type=EventType.LEAD_SUBMITTED,
                user=patient,
                clinic=clinic,
                object_type="lead",
                object_id=lead.id,
                metadata={
                    "reference_code": lead.reference_code,
                    "lead_type": lead.lead_type,
                    "service_name": lead.service_name,
                }
            )
        except Exception as exc:
            logger.warning("Failed to log lead analytics event for %s: %s", lead.reference_code, exc)

        return Response({
            "success": True,
            "lead_reference": lead.reference_code,
            "confirmation_message": "Your request has been sent and the clinic will contact you",
            "created_at": lead.created_at
        }, status=status.HTTP_201_CREATED)


class MyLeadsAPIView(generics.ListAPIView):
    """
    Returns leads belonging to the authenticated patient.
    Excludes clinic staff/admins without patient scope.
    """
    serializer_class = PatientLeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Lead.objects.none()

        if user.role not in (UserRole.PATIENT, UserRole.SUPER_ADMIN):
            raise PermissionDenied("Only patient accounts can view personal request history.")

        qs = Lead.objects.filter(patient=user).select_related(
            "clinic", "branch", "practitioner", "treatment", "offer", "product"
        )

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        return qs.order_by("-created_at")


class MyLeadDetailAPIView(generics.RetrieveAPIView):
    """
    Returns detail for a single lead belonging to the authenticated patient.
    Strictly scoped to request.user to prevent IDOR; returns 404 for cross-patient access.
    """
    serializer_class = PatientLeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Lead.objects.none()

        if user.role not in (UserRole.PATIENT, UserRole.SUPER_ADMIN):
            raise PermissionDenied("Only patient accounts can view personal request details.")

        return Lead.objects.filter(patient=user).select_related(
            "clinic", "branch", "practitioner", "treatment", "offer", "product"
        )


class MyLeadsCountAPIView(generics.GenericAPIView):
    """Returns simple total count for the authenticated patient."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: OpenApiResponse(description="Total patient leads count", response={"type": "object", "properties": {"count": {"type": "integer"}}})}
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.role not in (UserRole.PATIENT, UserRole.SUPER_ADMIN):
            raise PermissionDenied("Only patient accounts can view request counts.")

        total = Lead.objects.filter(patient=user).count()
        return Response({"count": total})
