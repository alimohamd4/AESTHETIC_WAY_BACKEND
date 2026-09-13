from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analytics.models import AnalyticsEvent, EventType
from apps.articles.models import Article, ContentStatus
from apps.clinics.models import ClinicBranch
from apps.clinics.portal_permissions import IsClinicPortalAccess, get_user_clinic
from apps.clinics.portal_serializers import (
    ClinicBranchPortalSerializer,
    ClinicProfilePortalSerializer,
)
from apps.leads.models import Lead, LeadStatus
from apps.offers.models import Offer, OfferStatus
from apps.practitioners.models import Practitioner, PractitionerStatus
from apps.products.models import Product
from apps.referrals.models import DiscountCodeStatus, ReferralDiscountCode
from apps.treatments.models import Treatment, TreatmentStatus


class ClinicDashboardAPIView(APIView):
    """
    Clinic dashboard telemetry and KPI overview.
    Aggregates communication taps, lead performance, and catalog metrics.
    Strictly scoped to the authenticated clinic user's assigned clinic.
    """
    permission_classes = [IsClinicPortalAccess]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs):
        clinic = get_user_clinic(request.user)

        # 1. Telemetry / Contact interactions
        events_qs = AnalyticsEvent.objects.filter(clinic=clinic)
        whatsapp_taps = events_qs.filter(event_type=EventType.WHATSAPP_TAP).count()
        call_taps = events_qs.filter(event_type=EventType.CALL_TAP).count()
        maps_taps = events_qs.filter(event_type=EventType.MAPS_TAP).count()
        profile_views = events_qs.filter(event_type=EventType.CLINIC_VIEW).count()

        # 2. Leads statistics
        leads_qs = Lead.objects.filter(clinic=clinic)
        total_leads = leads_qs.count()
        new_leads = leads_qs.filter(status=LeadStatus.NEW).count()
        contacted_leads = leads_qs.filter(status=LeadStatus.CONTACTED).count()
        closed_leads = leads_qs.filter(status=LeadStatus.CLOSED).count()

        conversion_rate = 0.0
        if total_leads > 0:
            conversion_rate = round((contacted_leads + closed_leads) / total_leads * 100.0, 1)

        # 3. Referral discount redemptions
        redeemed_codes = ReferralDiscountCode.objects.filter(
            redeemed_clinic=clinic,
            status=DiscountCodeStatus.USED,
        ).count()

        # 4. Catalog counts
        active_practitioners = Practitioner.objects.filter(
            clinic=clinic,
            status=PractitionerStatus.ACTIVE,
            deleted_at__isnull=True,
        ).count()
        active_treatments = Treatment.objects.filter(
            clinic=clinic,
            is_active=True,
            status=TreatmentStatus.ACTIVE,
            deleted_at__isnull=True,
        ).count()
        active_offers = Offer.objects.filter(
            clinic=clinic,
            is_active=True,
            status=OfferStatus.ACTIVE,
            deleted_at__isnull=True,
        ).count()
        active_products = Product.objects.filter(
            clinic=clinic,
            is_active=True,
            status=ContentStatus.ACTIVE,
            deleted_at__isnull=True,
        ).count()
        published_articles = Article.objects.filter(
            clinic=clinic,
            is_published=True,
            status=ContentStatus.ACTIVE,
            deleted_at__isnull=True,
        ).count()

        data = {
            "clinic_id": str(clinic.id),
            "clinic_name": clinic.name_en,
            "interactions": {
                "whatsapp_taps": whatsapp_taps,
                "call_taps": call_taps,
                "maps_taps": maps_taps,
                "profile_views": profile_views,
            },
            "leads": {
                "total": total_leads,
                "new": new_leads,
                "contacted": contacted_leads,
                "closed": closed_leads,
                "conversion_rate_percentage": conversion_rate,
            },
            "referrals": {
                "redeemed_discount_codes_count": redeemed_codes,
            },
            "catalog": {
                "active_practitioners_count": active_practitioners,
                "active_treatments_count": active_treatments,
                "active_offers_count": active_offers,
                "active_products_count": active_products,
                "published_articles_count": published_articles,
            },
            # Lead-only product specification: no internal booking engine
            "appointments": None,
        }

        return Response(data, status=status.HTTP_200_OK)


class ClinicProfileAPIView(generics.RetrieveUpdateAPIView):
    """
    Clinic profile endpoint for the clinic portal.
    GET /api/v1/clinic-portal/profile/
    PUT /api/v1/clinic-portal/profile/
    """
    permission_classes = [IsClinicPortalAccess]
    serializer_class = ClinicProfilePortalSerializer

    def get_object(self):
        return get_user_clinic(self.request.user)


class ClinicBranchPortalViewSet(viewsets.ModelViewSet):
    """
    Clinic portal CRUD for clinic branches.
    Enforces strict clinic scoping and anti-IDOR isolation.
    """
    permission_classes = [IsClinicPortalAccess]
    serializer_class = ClinicBranchPortalSerializer
    queryset = ClinicBranch.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not (
            self.request.user and self.request.user.is_authenticated
        ):
            return ClinicBranch.objects.none()

        clinic = get_user_clinic(self.request.user)
        return ClinicBranch.objects.filter(
            clinic=clinic,
            deleted_at__isnull=True,
        ).order_by("-is_main_branch", "name_en")

    def perform_create(self, serializer):
        clinic = get_user_clinic(self.request.user)
        serializer.save(clinic=clinic)

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.is_active = False
        instance.save(update_fields=["deleted_at", "is_active"])
