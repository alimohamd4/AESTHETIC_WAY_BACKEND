import uuid

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.clinics.models import ClinicStatus
from apps.offers.filters import OfferFilter
from apps.offers.models import Offer, OfferStatus
from apps.offers.serializers import PublicOfferSerializer


class OfferListAPIView(generics.ListAPIView):
    """
    Public endpoint to discover active promotional offers.
    Strictly excludes expired, inactive, or suspended offers.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicOfferSerializer
    filterset_class = OfferFilter
    search_fields = ["title_en", "title_ar", "description_en", "description_ar"]
    ordering_fields = ["created_at", "ends_at", "offer_price"]
    ordering = ["-created_at"]

    def get_queryset(self):
        now = timezone.now()
        return Offer.objects.filter(
            is_active=True,
            status=OfferStatus.ACTIVE,
            starts_at__lte=now,
            ends_at__gte=now,
            deleted_at__isnull=True,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True,
        ).select_related("clinic", "media_asset")


class OfferDetailAPIView(generics.RetrieveAPIView):
    """
    Public endpoint to view offer details.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicOfferSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        now = timezone.now()
        return Offer.objects.filter(
            is_active=True,
            status=OfferStatus.ACTIVE,
            starts_at__lte=now,
            ends_at__gte=now,
            deleted_at__isnull=True,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True,
        ).select_related("clinic", "media_asset")

    def get_object(self):
        lookup = self.kwargs.get(self.lookup_url_kwarg)
        try:
            val = uuid.UUID(str(lookup))
            return get_object_or_404(self.get_queryset(), pk=val)
        except (ValueError, TypeError):
            raise Http404 from None
