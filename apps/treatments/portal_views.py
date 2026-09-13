from django.utils import timezone
from rest_framework import filters, viewsets

from apps.clinics.portal_permissions import IsClinicPortalAccess, get_user_clinic
from apps.treatments.models import Treatment
from apps.treatments.portal_serializers import (
    ClinicTreatmentPortalSerializer,
)


class ClinicTreatmentPortalViewSet(viewsets.ModelViewSet):
    """
    Clinic portal CRUD for treatments.
    Strictly scoped to the authenticated clinic.
    """
    permission_classes = [IsClinicPortalAccess]
    serializer_class = ClinicTreatmentPortalSerializer
    queryset = Treatment.objects.none()
    filter_backends = [filters.SearchFilter]
    search_fields = ["name_en", "name_ar", "description_en", "description_ar"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not (
            self.request.user and self.request.user.is_authenticated
        ):
            return Treatment.objects.none()

        clinic = get_user_clinic(self.request.user)
        return Treatment.objects.filter(
            clinic=clinic,
            deleted_at__isnull=True,
        ).select_related("category").prefetch_related("practitioners").order_by("name_en")

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=["deleted_at", "is_active"])
