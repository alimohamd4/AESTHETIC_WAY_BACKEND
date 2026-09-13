import uuid

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.clinics.models import ClinicStatus
from apps.practitioners.filters import PractitionerFilter
from apps.practitioners.models import Practitioner, PractitionerStatus
from apps.practitioners.serializers import (
    PublicPractitionerDetailSerializer,
    PublicPractitionerListSerializer,
)


class PractitionerListAPIView(generics.ListAPIView):
    """
    Public endpoint to discover active practitioners.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicPractitionerListSerializer
    filterset_class = PractitionerFilter
    search_fields = [
        "name_en",
        "name_ar",
        "speciality_en",
        "speciality_ar",
        "title_en",
        "title_ar",
    ]
    ordering_fields = ["display_order", "name_en", "created_at"]
    ordering = ["display_order", "name_en"]

    def get_queryset(self):
        return Practitioner.objects.filter(
            status=PractitionerStatus.ACTIVE,
            deleted_at__isnull=True,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True,
        ).select_related("clinic")


class PractitionerDetailAPIView(generics.RetrieveAPIView):
    """
    Public endpoint to view a practitioner profile and performed treatments.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicPractitionerDetailSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return Practitioner.objects.filter(
            status=PractitionerStatus.ACTIVE,
            deleted_at__isnull=True,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True,
        ).select_related("clinic").prefetch_related("treatments")

    def get_object(self):
        lookup = self.kwargs.get(self.lookup_url_kwarg)
        try:
            val = uuid.UUID(str(lookup))
            return get_object_or_404(self.get_queryset(), pk=val)
        except (ValueError, TypeError):
            raise Http404 from None
