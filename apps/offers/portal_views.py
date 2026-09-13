from django.utils import timezone
from rest_framework import filters, viewsets

from apps.clinics.portal_permissions import IsClinicPortalAccess, get_user_clinic
from apps.offers.models import Offer
from apps.offers.portal_serializers import ClinicOfferPortalSerializer


class ClinicOfferPortalViewSet(viewsets.ModelViewSet):
    """
    Clinic portal CRUD for promotional offers.
    Strictly scoped to the authenticated clinic.
    """
    permission_classes = [IsClinicPortalAccess]
    serializer_class = ClinicOfferPortalSerializer
    queryset = Offer.objects.none()
    filter_backends = [filters.SearchFilter]
    search_fields = ["title_en", "title_ar", "description_en", "description_ar"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not (
            self.request.user and self.request.user.is_authenticated
        ):
            return Offer.objects.none()

        clinic = get_user_clinic(self.request.user)
        return Offer.objects.filter(
            clinic=clinic,
            deleted_at__isnull=True,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        clinic = get_user_clinic(self.request.user)
        serializer.save(clinic=clinic)

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=["deleted_at", "is_active"])
