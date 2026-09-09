from django.db.models import Case, When, Value, IntegerField, F, Q
from django.db.models.expressions import RawSQL
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.treatments.models import Category
from apps.offers.models import Offer
from apps.media.models import FeaturedAd
from apps.clinics.models import Clinic, ClinicStatus, SubscriptionTier
from apps.home.serializers import (
    CategorySerializer,
    OfferSerializer,
    FeaturedAdSerializer,
    PublicClinicSerializer,
)


class HomeFeedAPIView(APIView):
    """
    Home feed endpoint returning featured ads, categories, active offers, and nearby clinics.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("city", str, description="City to filter clinics and offers if lat/lng are missing"),
            OpenApiParameter("latitude", float, description="User latitude"),
            OpenApiParameter("longitude", float, description="User longitude"),
        ],
        responses={200: dict}
    )
    def get(self, request, *args, **kwargs):
        city = request.query_params.get("city")
        lat = request.query_params.get("latitude")
        lng = request.query_params.get("longitude")
        
        now = timezone.now()

        # 1. Categories
        categories = Category.objects.filter(is_active=True).order_by("display_order")[:8]

        # 2. Featured Ads
        # Order by tier then display_order
        # For simplicity, assuming display_order handles the tier ranking or we just return them.
        featured_ads = FeaturedAd.objects.filter(is_active=True).annotate(
            tier_rank=Case(
                When(subscription_tier=SubscriptionTier.VIP, then=Value(1)),
                When(subscription_tier=SubscriptionTier.FEATURED, then=Value(2)),
                When(subscription_tier=SubscriptionTier.BASIC, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        ).order_by("tier_rank", "display_order")[:5]

        # 3. Nearby Clinics Base Queryset
        clinics_qs = Clinic.objects.filter(
            status=ClinicStatus.ACTIVE, 
            deleted_at__isnull=True
        )

        if city and not (lat and lng):
            clinics_qs = clinics_qs.filter(city__iexact=city)

        # Ranking logic
        clinics_qs = clinics_qs.annotate(
            tier_rank=Case(
                When(subscription_tier=SubscriptionTier.VIP, then=Value(1)),
                When(subscription_tier=SubscriptionTier.FEATURED, then=Value(2)),
                When(subscription_tier=SubscriptionTier.BASIC, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        )

        has_location = bool(lat and lng)
        order_by_args = ["tier_rank"]

        if has_location:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                
                # Using PostGIS functions via RawSQL since fields are DecimalField
                # PostGIS ST_DistanceSphere returns distance in meters.
                # Cast longitude and latitude to float/double precision
                distance_sql = "ST_DistanceSphere(ST_MakePoint(CAST(longitude AS double precision), CAST(latitude AS double precision)), ST_MakePoint(%s, %s))"
                
                clinics_qs = clinics_qs.annotate(
                    distance=RawSQL(distance_sql, (lng_f, lat_f))
                )
                # Ensure we only calculate for rows that have lat/lng
                clinics_qs = clinics_qs.filter(latitude__isnull=False, longitude__isnull=False)
                order_by_args.append("distance")
            except ValueError:
                pass

        # 3rd sorting rule: rating
        # Django orders nulls last by default for descending order with F().desc(nulls_last=True)
        order_by_args.append(F("google_rating").desc(nulls_last=True))
        order_by_args.append("name_en")
        
        clinics_qs = clinics_qs.order_by(*order_by_args)[:10]

        # 4. Active Offers
        offers_qs = Offer.objects.filter(
            is_active=True,
            starts_at__lte=now,
            ends_at__gte=now,
            clinic__status=ClinicStatus.ACTIVE,
            clinic__deleted_at__isnull=True
        ).select_related("clinic")

        if city and not (lat and lng):
            offers_qs = offers_qs.filter(clinic__city__iexact=city)

        # For offers, we can apply a similar ranking based on the clinic's tier if needed
        # Or just order by most recently created
        offers_qs = offers_qs.order_by("-created_at")[:10]

        return Response({
            "featured_ads": FeaturedAdSerializer(featured_ads, many=True).data,
            "categories": CategorySerializer(categories, many=True).data,
            "active_offers": OfferSerializer(offers_qs, many=True).data,
            "nearby_clinics": PublicClinicSerializer(clinics_qs, many=True).data,
        })
