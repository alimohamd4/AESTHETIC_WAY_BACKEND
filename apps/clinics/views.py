import uuid

from django.db import connection
from django.db.models import Case, F, IntegerField, Value, When
from django.db.models.expressions import RawSQL
from django.shortcuts import get_object_or_404
from rest_framework import filters, generics
from rest_framework.permissions import AllowAny

from apps.clinics.filters import ClinicFilter
from apps.clinics.models import Clinic, ClinicStatus, SubscriptionTier
from apps.clinics.serializers import (
    PublicClinicDetailSerializer,
    PublicClinicListSerializer,
)


class ClinicListAPIView(generics.ListAPIView):
    """
    Public endpoint to discover clinics.
    Orders by internal subscription tier -> distance (if lat/lng provided) -> Google rating -> display_order -> name.
    STRICTLY EXCLUDES internal fields (subscription_tier, license, moderation).
    """
    permission_classes = [AllowAny]
    serializer_class = PublicClinicListSerializer
    filterset_class = ClinicFilter
    filter_backends = [
        *generics.ListAPIView.filter_backends,
        filters.SearchFilter,
    ]
    search_fields = ["name_en", "name_ar", "description_en", "description_ar", "city", "emirate"]

    def get_queryset(self):
        qs = Clinic.objects.filter(
            status=ClinicStatus.ACTIVE,
            deleted_at__isnull=True,
        )

        # 1. Internal tier ranking annotation (VIP=1, FEATURED=2, BASIC=3)
        qs = qs.annotate(
            tier_rank=Case(
                When(subscription_tier=SubscriptionTier.VIP, then=Value(1)),
                When(subscription_tier=SubscriptionTier.FEATURED, then=Value(2)),
                When(subscription_tier=SubscriptionTier.BASIC, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        )

        order_by_args = ["tier_rank"]

        lat = self.request.query_params.get("latitude") or self.request.query_params.get("lat")
        lng = self.request.query_params.get("longitude") or self.request.query_params.get("lng")

        if lat and lng:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                if connection.vendor == "postgresql":
                    distance_sql = (
                        "ST_DistanceSphere(ST_MakePoint(CAST(longitude AS double precision), "
                        "CAST(latitude AS double precision)), ST_MakePoint(%s, %s))"
                    )
                    qs = qs.annotate(distance=RawSQL(distance_sql, (lng_f, lat_f)))
                else:
                    # SQLite / standard SQL approximation for dev & test runs
                    distance_sql = (
                        "((CAST(latitude AS FLOAT) - %s) * (CAST(latitude AS FLOAT) - %s) + "
                        "(CAST(longitude AS FLOAT) - %s) * (CAST(longitude AS FLOAT) - %s))"
                    )
                    qs = qs.annotate(distance=RawSQL(distance_sql, (lat_f, lat_f, lng_f, lng_f)))

                qs = qs.filter(latitude__isnull=False, longitude__isnull=False)
                order_by_args.append("distance")
            except (ValueError, TypeError):
                pass

        # 3. Rating & secondary ordering
        order_by_args.append(F("google_rating").desc(nulls_last=True))
        order_by_args.append("display_order")
        order_by_args.append("name_en")

        return qs.order_by(*order_by_args)


class ClinicDetailAPIView(generics.RetrieveAPIView):
    """
    Public endpoint to view a clinic profile, including branches, active practitioners, and treatments.
    Supports lookup by UUID primary key or unique slug.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicClinicDetailSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return Clinic.objects.filter(
            status=ClinicStatus.ACTIVE,
            deleted_at__isnull=True,
        ).prefetch_related(
            "branches",
            "practitioners",
            "treatments__category",
        )

    def get_object(self):
        lookup = self.kwargs.get(self.lookup_url_kwarg)
        try:
            val = uuid.UUID(str(lookup))
            return get_object_or_404(self.get_queryset(), pk=val)
        except (ValueError, TypeError):
            return get_object_or_404(self.get_queryset(), slug=lookup)
