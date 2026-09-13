import uuid

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.clinics.models import ClinicStatus
from apps.products.filters import ProductFilter
from apps.products.models import ContentStatus, Product
from apps.products.serializers import PublicProductSerializer


class ProductListAPIView(generics.ListAPIView):
    """
    Public endpoint to discover clinic retail and skincare products (inquiry only).
    """
    permission_classes = [AllowAny]
    serializer_class = PublicProductSerializer
    filterset_class = ProductFilter
    search_fields = ["name_en", "name_ar", "description_en", "description_ar"]
    ordering_fields = ["created_at", "price", "name_en"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return Product.objects.filter(
            clinic__isnull=False,
            is_active=True,
            status=ContentStatus.ACTIVE,
            deleted_at__isnull=True,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True,
        ).select_related("clinic", "media_asset")


class ProductDetailAPIView(generics.RetrieveAPIView):
    """
    Public endpoint to view product details.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicProductSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return Product.objects.filter(
            clinic__isnull=False,
            is_active=True,
            status=ContentStatus.ACTIVE,
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
