import datetime
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

from apps.leads.models import Lead, LeadStatusHistory, LeadStatus
from apps.leads.serializers import (
    PatientLeadCreateSerializer,
    PatientLeadSerializer,
)


class LeadCreationThrottle(UserRateThrottle):
    rate = "5/hour"

class AnonLeadCreationThrottle(AnonRateThrottle):
    rate = "5/hour"


class LeadCreateAPIView(generics.CreateAPIView):
    """
    Patient endpoint to submit a lead.
    Guest leads are permitted but authenticated requests link to the user profile.
    """
    serializer_class = PatientLeadCreateSerializer
    permission_classes = [AllowAny]
    throttle_classes = [LeadCreationThrottle, AnonLeadCreationThrottle]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        clinic = serializer.validated_data.get("clinic")
        service_name = serializer.validated_data.get("service_name")
        patient_phone = serializer.validated_data.get("patient_phone")
        
        # Duplication check: exact same clinic and service for the same phone within 24h
        cutoff = timezone.now() - datetime.timedelta(hours=24)
        duplicate = Lead.objects.filter(
            clinic=clinic,
            service_name=service_name,
            patient_phone=patient_phone,
            created_at__gte=cutoff
        ).exists()
        
        if duplicate:
            return Response(
                {"detail": "A request for this service at this clinic was already submitted recently."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        # Proceed to save
        patient = request.user if request.user.is_authenticated else None
        
        lead = serializer.save(patient=patient, status=LeadStatus.NEW)
        
        # Write initial history log
        LeadStatusHistory.objects.create(
            lead=lead,
            status=LeadStatus.NEW,
            changed_by=patient
        )

        # --- Notifications (fire-and-forget, never blocks the response) ---
        from apps.notifications.service import NotificationService
        from apps.notifications.models import NotificationType

        # Notify clinic staff of the new lead (find first active clinic staff user)
        clinic_staff = lead.clinic.clinic_users.filter(is_active=True).select_related("user").first()
        if clinic_staff:
            NotificationService.send_async(
                recipient=clinic_staff.user,
                notification_type=NotificationType.NEW_LEAD_CLINIC,
                payload={"lead_id": str(lead.id), "reference": lead.reference_code, "patient_name": lead.patient_name},
            )

        # Notify patient of their lead confirmation
        if patient:
            NotificationService.send_async(
                recipient=patient,
                notification_type=NotificationType.LEAD_CONFIRMATION_PATIENT,
                payload={"lead_id": str(lead.id), "reference": lead.reference_code},
            )

        return Response({
            "success": True,
            "lead_reference": lead.reference_code,
            "confirmation_message": "Your request has been sent and the clinic will contact you",
            "created_at": lead.created_at
        }, status=status.HTTP_201_CREATED)


class MyLeadsAPIView(generics.ListAPIView):
    """Returns leads belonging to the authenticated patient."""
    serializer_class = PatientLeadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Lead.objects.filter(patient=self.request.user).select_related(
            "clinic", "branch", "practitioner", "offer", "product"
        )


class MyLeadsCountAPIView(generics.GenericAPIView):
    """Returns simple unread/total count for the authenticated patient."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        total = Lead.objects.filter(patient=request.user).count()
        return Response({"count": total})
