from django.utils import timezone
from rest_framework import filters, viewsets

from apps.clinics.portal_permissions import IsClinicPortalAccess, get_user_clinic
from apps.practitioners.models import Practitioner, PractitionerStatus
from apps.practitioners.portal_serializers import (
    ClinicPractitionerPortalSerializer,
)


class ClinicPractitionerPortalViewSet(viewsets.ModelViewSet):
    """
    Clinic portal CRUD for medical practitioners.
    Strictly scoped to the authenticated clinic.
    """
    permission_classes = [IsClinicPortalAccess]
    serializer_class = ClinicPractitionerPortalSerializer
    queryset = Practitioner.objects.none()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name_en", "name_ar", "speciality_en", "speciality_ar"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not (
            self.request.user and self.request.user.is_authenticated
        ):
            return Practitioner.objects.none()

        clinic = get_user_clinic(self.request.user)
        return Practitioner.objects.filter(
            clinic=clinic,
            deleted_at__isnull=True,
        ).order_by("display_order", "name_en")

    def perform_create(self, serializer):
        clinic = get_user_clinic(self.request.user)
        serializer.save(clinic=clinic)

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.status = PractitionerStatus.INACTIVE
        instance.save(update_fields=["deleted_at", "status"])
