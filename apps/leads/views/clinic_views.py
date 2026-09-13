from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import UserRole
from apps.leads.models import Lead, LeadStatusHistory
from apps.leads.serializers import (
    ClinicLeadSerializer,
    LeadNoteSerializer,
    LeadStatusUpdateSerializer,
)


class ClinicLeadViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
):
    """
    Clinic portal leads endpoint.
    Provides GET (list, retrieve), PATCH (status), and POST (notes).
    Enforces isolation: clinics only see their own leads.
    Super Admins can see all leads but cannot mutate them.
    """
    serializer_class = ClinicLeadSerializer
    permission_classes = [IsAuthenticated]
    queryset = Lead.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not (
            self.request.user and self.request.user.is_authenticated
        ):
            return Lead.objects.none()

        user = self.request.user

        # Super admin sees all leads
        if user.role == UserRole.SUPER_ADMIN:
            return Lead.objects.all().prefetch_related("internal_notes", "status_history")

        # Clinic user sees leads for their assigned clinics
        if user.is_clinic_user:
            clinic_ids = user.clinic_memberships.filter(is_active=True).values_list("clinic_id", flat=True)
            return Lead.objects.filter(clinic_id__in=clinic_ids).prefetch_related(
                "internal_notes", "status_history"
            )

        # Patients shouldn't access this endpoint
        return Lead.objects.none()

    def partial_update(self, request, *args, **kwargs):
        """PATCH operational status."""
        if request.user.role == UserRole.SUPER_ADMIN:
            raise PermissionDenied("Super Admins are read-only for operational status.")

        lead = self.get_object()
        serializer = LeadStatusUpdateSerializer(lead, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        # Only create history if status actually changed
        new_status = serializer.validated_data.get("status")
        if new_status and new_status != lead.status:
            serializer.save()
            LeadStatusHistory.objects.create(
                lead=lead,
                status=new_status,
                changed_by=request.user
            )
            return Response(serializer.data)

        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def notes(self, request, pk=None):
        """POST internal clinic note."""
        if request.user.role == UserRole.SUPER_ADMIN:
            raise PermissionDenied("Super Admins cannot add operational notes.")

        lead = self.get_object()
        serializer = LeadNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(lead=lead, author=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
