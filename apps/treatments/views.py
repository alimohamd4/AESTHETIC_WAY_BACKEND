import uuid

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import filters, generics
from rest_framework.permissions import AllowAny

from apps.clinics.models import ClinicStatus
from apps.treatments.filters import TreatmentFilter
from apps.treatments.models import Category, Treatment, TreatmentStatus
from apps.treatments.serializers import (
    PublicCategorySerializer,
    PublicTreatmentDetailSerializer,
    PublicTreatmentListSerializer,
)


class CategoryListAPIView(generics.ListAPIView):
    """
    Public endpoint to list active treatment categories ordered by display_order.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicCategorySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ["name_en", "name_ar"]

    def get_queryset(self):
        return Category.objects.filter(is_active=True).order_by("display_order", "name_en")


class TreatmentListAPIView(generics.ListAPIView):
    """
    Public endpoint to discover treatments offered by active clinics.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicTreatmentListSerializer
    filterset_class = TreatmentFilter
    search_fields = ["name_en", "name_ar", "description_en", "description_ar"]
    ordering_fields = ["name_en", "price", "created_at"]
    ordering = ["name_en"]

    def get_queryset(self):
        return Treatment.objects.filter(
            is_active=True,
            status=TreatmentStatus.ACTIVE,
            deleted_at__isnull=True,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True,
            category__is_active=True,
        ).select_related("clinic", "category")


class TreatmentDetailAPIView(generics.RetrieveAPIView):
    """
    Public endpoint to retrieve a single treatment profile.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicTreatmentDetailSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return Treatment.objects.filter(
            is_active=True,
            status=TreatmentStatus.ACTIVE,
            deleted_at__isnull=True,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True,
            category__is_active=True,
        ).select_related("clinic", "category").prefetch_related("practitioners")

    def get_object(self):
        lookup = self.kwargs.get(self.lookup_url_kwarg)
        try:
            val = uuid.UUID(str(lookup))
            return get_object_or_404(self.get_queryset(), pk=val)
        except (ValueError, TypeError):
            raise Http404 from None
