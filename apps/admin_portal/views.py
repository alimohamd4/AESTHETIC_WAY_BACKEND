"""
AESTHETIC WAY Backend - Admin Portal Views (Phase 16)
"""
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.accounts.models import User, UserRole
from apps.admin_portal.models import AdminActionType, AdminAuditLog
from apps.admin_portal.permissions import IsSuperAdmin
from apps.admin_portal.serializers import (
    ALLOWED_SETTING_KEYS,
    AdminAuditLogSerializer,
    AdminClinicActionSerializer,
    AdminClinicDetailSerializer,
    AdminClinicListSerializer,
    AdminClinicUpdateSerializer,
    AdminLeadSerializer,
    AdminModerationActionSerializer,
    AdminModerationItemSerializer,
    AdminPlatformSettingUpdateSerializer,
    ClinicStatusUpdateSerializer,
    ClinicSubscriptionUpdateSerializer,
    ContentModerationSerializer,
    PlatformSettingSerializer,
)
from apps.analytics.models import AnalyticsEvent, EventType
from apps.app_config.models import PlatformSetting
from apps.articles.models import Article
from apps.articles.serializers import PublicArticleDetailSerializer
from apps.clinics.models import Clinic, ClinicStatus, SubscriptionTier
from apps.leads.models import Lead, LeadStatus
from apps.offers.models import Offer
from apps.offers.serializers import PublicOfferSerializer
from apps.practitioners.models import Practitioner
from apps.products.models import Product
from apps.products.serializers import PublicProductSerializer
from apps.referrals.models import (
    DiscountCodeStatus,
    ReferralDiscountCode,
    ReferralInvite,
    ReferralPointsLedger,
)
from apps.treatments.models import Treatment


class AdminStandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


# =====================================================================
# 1. Platform Dashboard
# =====================================================================

@extend_schema(responses={200: dict})
class AdminDashboardAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get(self, request, *args, **kwargs):
        # Clinics aggregates
        clinic_stats = Clinic.objects.filter(deleted_at__isnull=True).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status=ClinicStatus.ACTIVE)),
            suspended=Count("id", filter=Q(status=ClinicStatus.SUSPENDED)),
            pending=Count("id", filter=Q(status=ClinicStatus.PENDING)),
            tier_basic=Count("id", filter=Q(subscription_tier=SubscriptionTier.BASIC)),
            tier_featured=Count("id", filter=Q(subscription_tier=SubscriptionTier.FEATURED)),
            tier_vip=Count("id", filter=Q(subscription_tier=SubscriptionTier.VIP)),
            featured_total=Count("id", filter=Q(subscription_tier__in=[SubscriptionTier.FEATURED, SubscriptionTier.VIP])),
        )

        total_clinics = clinic_stats["total"]
        active_clinics = clinic_stats["active"]
        suspended_clinics = clinic_stats["suspended"]
        pending_clinics = clinic_stats["pending"]

        # Catalog & users aggregates
        total_patients = User.objects.filter(role=UserRole.PATIENT, is_active=True).count()
        total_practitioners = Practitioner.objects.filter(deleted_at__isnull=True).count()
        total_treatments = Treatment.objects.filter(deleted_at__isnull=True).count()
        total_offers = Offer.objects.filter(deleted_at__isnull=True).count()
        total_products = Product.objects.filter(deleted_at__isnull=True).count()
        total_articles = Article.objects.filter(deleted_at__isnull=True).count()

        # Leads aggregates
        lead_stats = Lead.objects.aggregate(
            total=Count("id"),
            new=Count("id", filter=Q(status=LeadStatus.NEW)),
            contacted=Count("id", filter=Q(status=LeadStatus.CONTACTED)),
            closed=Count("id", filter=Q(status=LeadStatus.CLOSED)),
        )
        total_leads = lead_stats["total"]
        leads_by_status = {
            "new": lead_stats["new"],
            "contacted": lead_stats["contacted"],
            "closed": lead_stats["closed"],
        }
        completed_leads = lead_stats["closed"]
        scheduled_leads = lead_stats["contacted"]
        conversion_percentage = (
            round((completed_leads / total_leads * 100), 2) if total_leads > 0 else 0.0
        )

        # Referrals & Analytics aggregates
        total_referrals = ReferralInvite.objects.count()
        total_redeemed_referral_codes = ReferralDiscountCode.objects.filter(
            status=DiscountCodeStatus.USED
        ).count()
        total_analytics_events = AnalyticsEvent.objects.count()

        active_subscription_tiers = {
            "basic": clinic_stats["tier_basic"],
            "featured": clinic_stats["tier_featured"],
            "vip": clinic_stats["tier_vip"],
        }
        featured_clinics = clinic_stats["featured_total"]

        data = {
            "total_clinics": total_clinics,
            "active_clinics": active_clinics,
            "suspended_clinics": suspended_clinics,
            "pending_clinics": pending_clinics,
            "total_patients": total_patients,
            "total_practitioners": total_practitioners,
            "total_treatments": total_treatments,
            "total_offers": total_offers,
            "total_products": total_products,
            "total_articles": total_articles,
            "total_leads": total_leads,
            "completed_leads": completed_leads,
            "scheduled_leads": scheduled_leads,
            "leads_by_status": leads_by_status,
            "conversion_percentage": conversion_percentage,
            "total_referrals": total_referrals,
            "total_redeemed_referral_codes": total_redeemed_referral_codes,
            "total_analytics_events": total_analytics_events,
            "active_subscription_tiers": active_subscription_tiers,
            "featured_clinics": featured_clinics,
        }
        return Response(data)


# =====================================================================
# 2. Clinic Administration ViewSet
# =====================================================================

class AdminClinicViewSet(viewsets.ModelViewSet):
    """
    Platform-level clinic administration.
    Only Super Admins may access, list, inspect, or mutate clinics.
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
    pagination_class = AdminStandardPagination
    http_method_names = ["get", "patch", "post", "head", "options"]
    queryset = Clinic.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Clinic.objects.none()
        include_deleted = self.request.query_params.get("include_deleted", "").lower() == "true"
        qs = Clinic.objects.all()
        if not include_deleted:
            qs = qs.filter(deleted_at__isnull=True)

        # Annotate counts to avoid N+1 queries
        qs = qs.annotate(
            branches_count=Count("branches", filter=Q(branches__deleted_at__isnull=True), distinct=True),
            practitioners_count=Count("practitioners", filter=Q(practitioners__deleted_at__isnull=True), distinct=True),
            treatments_count=Count("treatments", filter=Q(treatments__deleted_at__isnull=True), distinct=True),
            offers_count=Count("offers", filter=Q(offers__deleted_at__isnull=True), distinct=True),
            products_count=Count("products", filter=Q(products__deleted_at__isnull=True), distinct=True),
            articles_count=Count("articles", filter=Q(articles__deleted_at__isnull=True), distinct=True),
            leads_count=Count("leads", distinct=True),
        )

        # Filters
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status__iexact=status_param)

        tier_param = self.request.query_params.get("tier") or self.request.query_params.get("subscription_tier")
        if tier_param:
            qs = qs.filter(subscription_tier__iexact=tier_param)

        city_param = self.request.query_params.get("city")
        if city_param:
            qs = qs.filter(city__icontains=city_param)

        search_param = self.request.query_params.get("search")
        if search_param:
            qs = qs.filter(
                Q(name_en__icontains=search_param)
                | Q(name_ar__icontains=search_param)
                | Q(slug__icontains=search_param)
                | Q(license_number__icontains=search_param)
            )

        ordering = self.request.query_params.get("ordering", "-created_at")
        allowed_orderings = [
            "created_at", "-created_at",
            "name_en", "-name_en",
            "display_order", "-display_order",
            "subscription_tier", "-subscription_tier",
            "status", "-status",
        ]
        if ordering in allowed_orderings:
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by("-created_at")

        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AdminClinicDetailSerializer
        if self.action in ["partial_update", "update"]:
            return AdminClinicUpdateSerializer
        return AdminClinicListSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Compute lead statistics for this clinic
        lead_stats = Lead.objects.filter(clinic=instance).aggregate(
            new=Count("id", filter=Q(status=LeadStatus.NEW)),
            contacted=Count("id", filter=Q(status=LeadStatus.CONTACTED)),
            closed=Count("id", filter=Q(status=LeadStatus.CLOSED)),
        )
        instance.leads_by_status = {
            "new": lead_stats["new"],
            "contacted": lead_stats["contacted"],
            "closed": lead_stats["closed"],
        }
        serializer = AdminClinicDetailSerializer(instance)
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        clinic = self.get_object()
        serializer = AdminClinicUpdateSerializer(clinic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        old_tier = clinic.subscription_tier
        old_status = clinic.status

        with transaction.atomic():
            updated_clinic = serializer.save()

            new_tier = updated_clinic.subscription_tier
            new_status = updated_clinic.status

            # Audit tier changes
            if old_tier != new_tier:
                AdminAuditLog.objects.create(
                    admin=request.user,
                    action_type=AdminActionType.UPDATE_SUBSCRIPTION,
                    entity_type="Clinic",
                    entity_id=clinic.id,
                    details={"old_tier": old_tier, "new_tier": new_tier},
                )

            # Audit status changes
            if old_status != new_status:
                action_type = (
                    AdminActionType.SUSPEND_CLINIC
                    if new_status == ClinicStatus.SUSPENDED
                    else AdminActionType.ACTIVATE_CLINIC
                )
                AdminAuditLog.objects.create(
                    admin=request.user,
                    action_type=action_type,
                    entity_type="Clinic",
                    entity_id=clinic.id,
                    details={"old_status": old_status, "new_status": new_status},
                )

        return Response(AdminClinicDetailSerializer(updated_clinic).data)

    @extend_schema(request=AdminClinicActionSerializer, responses={200: dict})
    @action(methods=["post"], detail=True, url_path="suspend")
    def suspend(self, request, pk=None):
        clinic = self.get_object()
        serializer = AdminClinicActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data.get("reason") or serializer.validated_data.get("moderation_notes", "")
        old_status = clinic.status

        with transaction.atomic():
            clinic.status = ClinicStatus.SUSPENDED
            if reason:
                clinic.moderation_notes = reason
            clinic.moderated_by = request.user
            clinic.moderated_at = timezone.now()
            clinic.save(update_fields=["status", "moderation_notes", "moderated_by", "moderated_at", "updated_at"])

            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=AdminActionType.SUSPEND_CLINIC,
                entity_type="Clinic",
                entity_id=clinic.id,
                details={"old_status": old_status, "new_status": ClinicStatus.SUSPENDED, "reason": reason},
            )

        return Response({
            "status": "success",
            "clinic_id": clinic.id,
            "new_status": clinic.status,
            "moderation_notes": clinic.moderation_notes,
        })

    @extend_schema(request=AdminClinicActionSerializer, responses={200: dict})
    @action(methods=["post"], detail=True, url_path="activate")
    def activate(self, request, pk=None):
        clinic = self.get_object()
        serializer = AdminClinicActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data.get("reason") or serializer.validated_data.get("moderation_notes", "")
        old_status = clinic.status

        with transaction.atomic():
            clinic.status = ClinicStatus.ACTIVE
            if reason:
                clinic.moderation_notes = reason
            clinic.moderated_by = request.user
            clinic.moderated_at = timezone.now()
            clinic.save(update_fields=["status", "moderation_notes", "moderated_by", "moderated_at", "updated_at"])

            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=AdminActionType.ACTIVATE_CLINIC,
                entity_type="Clinic",
                entity_id=clinic.id,
                details={"old_status": old_status, "new_status": ClinicStatus.ACTIVE, "reason": reason},
            )

        return Response({
            "status": "success",
            "clinic_id": clinic.id,
            "new_status": clinic.status,
            "moderation_notes": clinic.moderation_notes,
        })

    @extend_schema(request=AdminClinicActionSerializer, responses={200: dict})
    @action(methods=["post"], detail=True, url_path="verify")
    def verify(self, request, pk=None):
        clinic = self.get_object()
        serializer = AdminClinicActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reason = serializer.validated_data.get("reason") or serializer.validated_data.get("moderation_notes") or "Verified by Super Admin"
        old_status = clinic.status

        with transaction.atomic():
            clinic.status = ClinicStatus.ACTIVE
            clinic.moderation_notes = reason
            clinic.moderated_by = request.user
            clinic.moderated_at = timezone.now()
            clinic.save(update_fields=["status", "moderation_notes", "moderated_by", "moderated_at", "updated_at"])

            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=AdminActionType.VERIFY_CLINIC,
                entity_type="Clinic",
                entity_id=clinic.id,
                details={"old_status": old_status, "new_status": ClinicStatus.ACTIVE, "verified": True, "notes": reason},
            )

        return Response({
            "status": "success",
            "clinic_id": clinic.id,
            "new_status": clinic.status,
            "is_verified": True,
            "moderation_notes": clinic.moderation_notes,
        })

    @extend_schema(responses={200: AdminAuditLogSerializer(many=True)})
    @action(methods=["get"], detail=True, url_path="audit")
    def audit(self, request, pk=None):
        clinic = self.get_object()
        logs = AdminAuditLog.objects.filter(entity_type="Clinic", entity_id=clinic.id).order_by("-created_at")
        paginator = AdminStandardPagination()
        page = paginator.paginate_queryset(logs, request)
        serializer = AdminAuditLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# =====================================================================
# Backward Compatibility Views for Clinic Status & Subscription
# =====================================================================

class AdminClinicStatusAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @extend_schema(request=ClinicStatusUpdateSerializer, responses={200: dict})
    def patch(self, request, pk, *args, **kwargs):
        clinic = get_object_or_404(Clinic, pk=pk)
        serializer = ClinicStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = clinic.status
        new_status = serializer.validated_data["status"]

        with transaction.atomic():
            clinic.status = new_status
            clinic.moderation_notes = serializer.validated_data.get("moderation_notes", clinic.moderation_notes)
            clinic.moderated_by = request.user
            clinic.moderated_at = timezone.now()
            clinic.save(update_fields=["status", "moderation_notes", "moderated_by", "moderated_at", "updated_at"])

            # Log audit
            action_type = (
                AdminActionType.SUSPEND_CLINIC if new_status == ClinicStatus.SUSPENDED
                else (AdminActionType.ACTIVATE_CLINIC if new_status == ClinicStatus.ACTIVE else AdminActionType.UPDATE_SETTINGS)
            )
            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=action_type,
                entity_type="Clinic",
                entity_id=clinic.id,
                details={"old_status": old_status, "new_status": new_status},
            )

        return Response({"status": "success", "new_status": clinic.status})


class AdminClinicSubscriptionAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @extend_schema(request=ClinicSubscriptionUpdateSerializer, responses={200: dict})
    def patch(self, request, pk, *args, **kwargs):
        clinic = get_object_or_404(Clinic, pk=pk)
        serializer = ClinicSubscriptionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_tier = clinic.subscription_tier
        new_tier = serializer.validated_data["subscription_tier"]

        with transaction.atomic():
            clinic.subscription_tier = new_tier
            clinic.save(update_fields=["subscription_tier", "updated_at"])

            # Log audit
            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=AdminActionType.UPDATE_SUBSCRIPTION,
                entity_type="Clinic",
                entity_id=clinic.id,
                details={"old_tier": old_tier, "new_tier": new_tier},
            )

        return Response({"status": "success", "new_tier": clinic.subscription_tier})


# =====================================================================
# 3. Admin Lead Supervision (Read-Only)
# =====================================================================

class AdminLeadAPIView(generics.ListAPIView):
    """
    Read-only supervision view of platform-wide leads.
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
    serializer_class = AdminLeadSerializer
    pagination_class = AdminStandardPagination
    queryset = Lead.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Lead.objects.none()
        qs = Lead.objects.all().select_related(
            "clinic", "branch", "practitioner", "treatment", "offer", "product"
        ).order_by("-created_at")

        # Filters
        clinic_param = self.request.query_params.get("clinic")
        if clinic_param:
            qs = qs.filter(clinic_id=clinic_param)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status__iexact=status_param)

        lead_type_param = self.request.query_params.get("lead_type")
        if lead_type_param:
            qs = qs.filter(lead_type__iexact=lead_type_param)

        ref_param = self.request.query_params.get("reference_code")
        if ref_param:
            qs = qs.filter(reference_code__iexact=ref_param)

        date_from = self.request.query_params.get("date_from") or self.request.query_params.get("from")
        if date_from:
            try:
                d = datetime.strptime(date_from, "%Y-%m-%d").date()
                qs = qs.filter(created_at__gte=timezone.make_aware(datetime.combine(d, datetime.min.time())))
            except ValueError:
                pass

        date_to = self.request.query_params.get("date_to") or self.request.query_params.get("to")
        if date_to:
            try:
                d = datetime.strptime(date_to, "%Y-%m-%d").date()
                qs = qs.filter(created_at__lte=timezone.make_aware(datetime.combine(d, datetime.max.time())))
            except ValueError:
                pass

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(reference_code__icontains=search)
                | Q(patient_name__icontains=search)
                | Q(patient_phone__icontains=search)
                | Q(clinic__name_en__icontains=search)
                | Q(clinic__name_ar__icontains=search)
            )

        return qs


class AdminLeadDetailAPIView(generics.RetrieveAPIView):
    """
    Read-only detail view for a specific lead.
    Returns 404 for nonexistent resources.
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
    serializer_class = AdminLeadSerializer
    queryset = Lead.objects.all().select_related(
        "clinic", "branch", "practitioner", "treatment", "offer", "product"
    )


# =====================================================================
# 4. Content Moderation Views & Unified Queue
# =====================================================================

class AdminModerationQueueAPIView(views.APIView):
    """
    Unified moderation queue across Offers, Products, and Articles.
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @extend_schema(responses={200: AdminModerationItemSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        content_type = request.query_params.get("content_type", "").lower()
        status_filter = request.query_params.get("status")
        clinic_filter = request.query_params.get("clinic")
        date_from = request.query_params.get("date_from") or request.query_params.get("from")
        date_to = request.query_params.get("date_to") or request.query_params.get("to")

        items = []

        # Offers
        if not content_type or content_type == "offer":
            qs = Offer.objects.filter(deleted_at__isnull=True).select_related("clinic")
            if status_filter:
                qs = qs.filter(status__iexact=status_filter)
            if clinic_filter:
                qs = qs.filter(clinic_id=clinic_filter)
            if date_from:
                qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(created_at__date__lte=date_to)

            for o in qs.order_by("-created_at")[:100]:
                items.append({
                    "content_type": "offer",
                    "id": o.id,
                    "title": o.title_en,
                    "status": o.status,
                    "clinic_id": o.clinic_id,
                    "clinic_name": o.clinic.name_en if o.clinic else None,
                    "price": o.offer_price,
                    "created_at": o.created_at,
                    "updated_at": o.updated_at,
                })

        # Products
        if not content_type or content_type == "product":
            qs = Product.objects.filter(deleted_at__isnull=True).select_related("clinic")
            if status_filter:
                qs = qs.filter(status__iexact=status_filter)
            if clinic_filter:
                qs = qs.filter(clinic_id=clinic_filter)
            if date_from:
                qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(created_at__date__lte=date_to)

            for p in qs.order_by("-created_at")[:100]:
                items.append({
                    "content_type": "product",
                    "id": p.id,
                    "title": p.name_en,
                    "status": p.status,
                    "clinic_id": p.clinic_id,
                    "clinic_name": p.clinic.name_en if p.clinic else None,
                    "price": p.price,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                })

        # Articles
        if not content_type or content_type == "article":
            qs = Article.objects.filter(deleted_at__isnull=True).select_related("clinic")
            if status_filter:
                qs = qs.filter(status__iexact=status_filter)
            if clinic_filter:
                qs = qs.filter(clinic_id=clinic_filter)
            if date_from:
                qs = qs.filter(created_at__date__gte=date_from)
            if date_to:
                qs = qs.filter(created_at__date__lte=date_to)

            for a in qs.order_by("-created_at")[:100]:
                items.append({
                    "content_type": "article",
                    "id": a.id,
                    "title": a.title_en,
                    "status": a.status,
                    "clinic_id": a.clinic_id,
                    "clinic_name": a.clinic.name_en if a.clinic else None,
                    "price": None,
                    "created_at": a.created_at,
                    "updated_at": a.updated_at,
                })

        # Sort combined items by updated_at descending
        items.sort(key=lambda x: x["updated_at"], reverse=True)

        paginator = AdminStandardPagination()
        page = paginator.paginate_queryset(items, request)
        serializer = AdminModerationItemSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class BaseContentModerationViewSet(viewsets.ReadOnlyModelViewSet):
    """Base ViewSet for Super Admin content inspection and moderation."""
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
    pagination_class = AdminStandardPagination

    model_class = None
    entity_type_name = ""

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or self.model_class is None:
            return self.model_class.objects.none() if self.model_class else Offer.objects.none()
        qs = self.model_class.objects.filter(deleted_at__isnull=True).order_by("-created_at")
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status__iexact=status_param)
        clinic_param = self.request.query_params.get("clinic")
        if clinic_param:
            qs = qs.filter(clinic_id=clinic_param)
        return qs

    def execute_moderation(self, request, instance, target_status, notes=""):
        old_status = getattr(instance, "status", None)
        with transaction.atomic():
            instance.status = target_status
            update_fields = ["status", "updated_at"]
            if hasattr(instance, "is_active"):
                instance.is_active = (target_status == "active")
                update_fields.append("is_active")
            instance.save(update_fields=update_fields)

            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=AdminActionType.MODERATE_CONTENT,
                entity_type=self.entity_type_name,
                entity_id=instance.id,
                details={
                    "old_status": old_status,
                    "new_status": target_status,
                    "notes": notes,
                },
            )
        return Response({
            "status": "success",
            "id": instance.id,
            "new_status": target_status,
            "entity_type": self.entity_type_name,
        })

    @action(methods=["post"], detail=True, url_path="moderate")
    def moderate(self, request, pk=None):
        instance = self.get_object()
        serializer = AdminModerationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_status = serializer.get_target_status()
        notes = serializer.validated_data.get("moderation_notes", "")
        return self.execute_moderation(request, instance, target_status, notes)

    @action(methods=["post"], detail=True, url_path="approve")
    def approve(self, request, pk=None):
        instance = self.get_object()
        notes = request.data.get("moderation_notes", "Approved by Super Admin")
        return self.execute_moderation(request, instance, "active", notes)

    @action(methods=["post"], detail=True, url_path="reject")
    def reject(self, request, pk=None):
        instance = self.get_object()
        notes = request.data.get("moderation_notes", "Rejected by Super Admin")
        return self.execute_moderation(request, instance, "rejected", notes)

    @action(methods=["post"], detail=True, url_path="suspend")
    def suspend(self, request, pk=None):
        instance = self.get_object()
        notes = request.data.get("moderation_notes", "Suspended by Super Admin")
        return self.execute_moderation(request, instance, "suspended", notes)

    @action(methods=["post"], detail=True, url_path="restore")
    def restore(self, request, pk=None):
        instance = self.get_object()
        notes = request.data.get("moderation_notes", "Restored by Super Admin")
        return self.execute_moderation(request, instance, "active", notes)


@extend_schema_view(
    list=extend_schema(operation_id="admin_offers_list"),
    retrieve=extend_schema(operation_id="admin_offers_detail"),
    moderate=extend_schema(operation_id="admin_offers_moderate", request=AdminModerationActionSerializer, responses={200: dict}),
    approve=extend_schema(operation_id="admin_offers_approve", request=AdminModerationActionSerializer, responses={200: dict}),
    reject=extend_schema(operation_id="admin_offers_reject", request=AdminModerationActionSerializer, responses={200: dict}),
    suspend=extend_schema(operation_id="admin_offers_suspend", request=AdminModerationActionSerializer, responses={200: dict}),
    restore=extend_schema(operation_id="admin_offers_restore", request=AdminModerationActionSerializer, responses={200: dict}),
)
class AdminOfferModerationViewSet(BaseContentModerationViewSet):
    model_class = Offer
    queryset = Offer.objects.none()
    serializer_class = PublicOfferSerializer
    entity_type_name = "Offer"

    def get_serializer_class(self):
        return PublicOfferSerializer


@extend_schema_view(
    list=extend_schema(operation_id="admin_products_list"),
    retrieve=extend_schema(operation_id="admin_products_detail"),
    moderate=extend_schema(operation_id="admin_products_moderate", request=AdminModerationActionSerializer, responses={200: dict}),
    approve=extend_schema(operation_id="admin_products_approve", request=AdminModerationActionSerializer, responses={200: dict}),
    reject=extend_schema(operation_id="admin_products_reject", request=AdminModerationActionSerializer, responses={200: dict}),
    suspend=extend_schema(operation_id="admin_products_suspend", request=AdminModerationActionSerializer, responses={200: dict}),
    restore=extend_schema(operation_id="admin_products_restore", request=AdminModerationActionSerializer, responses={200: dict}),
)
class AdminProductModerationViewSet(BaseContentModerationViewSet):
    model_class = Product
    queryset = Product.objects.none()
    serializer_class = PublicProductSerializer
    entity_type_name = "Product"

    def get_serializer_class(self):
        return PublicProductSerializer


@extend_schema_view(
    list=extend_schema(operation_id="admin_articles_list"),
    retrieve=extend_schema(operation_id="admin_articles_detail"),
    moderate=extend_schema(operation_id="admin_articles_moderate", request=AdminModerationActionSerializer, responses={200: dict}),
    approve=extend_schema(operation_id="admin_articles_approve", request=AdminModerationActionSerializer, responses={200: dict}),
    reject=extend_schema(operation_id="admin_articles_reject", request=AdminModerationActionSerializer, responses={200: dict}),
    suspend=extend_schema(operation_id="admin_articles_suspend", request=AdminModerationActionSerializer, responses={200: dict}),
    restore=extend_schema(operation_id="admin_articles_restore", request=AdminModerationActionSerializer, responses={200: dict}),
)
class AdminArticleModerationViewSet(BaseContentModerationViewSet):
    model_class = Article
    queryset = Article.objects.none()
    serializer_class = PublicArticleDetailSerializer
    entity_type_name = "Article"

    def get_serializer_class(self):
        return PublicArticleDetailSerializer


class AdminModerationAPIView(views.APIView):
    """
    Legacy moderation API retained for backward compatibility:
    PATCH /api/v1/admin/moderate/<model_name>/<pk>/
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    def get_model(self, model_name):
        models = {
            "offer": Offer,
            "product": Product,
            "article": Article,
        }
        return models.get(model_name.lower())

    @extend_schema(request=ContentModerationSerializer, responses={200: dict})
    def patch(self, request, model_name, pk, *args, **kwargs):
        ModelClass = self.get_model(model_name)
        if not ModelClass:
            return Response({"detail": "Invalid model type."}, status=status.HTTP_400_BAD_REQUEST)

        instance = get_object_or_404(ModelClass, pk=pk)

        serializer = ContentModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = getattr(instance, "status", None)
        new_status = serializer.validated_data["status"]

        with transaction.atomic():
            instance.status = new_status
            update_fields = ["status"]
            if hasattr(instance, "is_active"):
                instance.is_active = (new_status == "active")
                update_fields.append("is_active")
            instance.save(update_fields=update_fields)

            # Log audit
            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=AdminActionType.MODERATE_CONTENT,
                entity_type=ModelClass.__name__,
                entity_id=instance.id,
                details={"old_status": old_status, "new_status": new_status},
            )

        return Response({"status": "success", "new_status": new_status})


# =====================================================================
# 5. Platform Analytics
# =====================================================================

class AdminPlatformAnalyticsAPIView(views.APIView):
    """
    Platform-wide analytics aggregation with date range filtering.
    GET /api/v1/admin/analytics/?from=YYYY-MM-DD&to=YYYY-MM-DD
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs):
        from_param = request.query_params.get("from") or request.query_params.get("date_from")
        to_param = request.query_params.get("to") or request.query_params.get("date_to")

        local_now = timezone.localtime(timezone.now())
        date_to = local_now.date()
        date_from = date_to - timedelta(days=30)

        if from_param:
            try:
                date_from = datetime.strptime(from_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": {"code": "INVALID_DATE", "message": "Invalid 'from' date format. Use YYYY-MM-DD."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if to_param:
            try:
                date_to = datetime.strptime(to_param, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": {"code": "INVALID_DATE", "message": "Invalid 'to' date format. Use YYYY-MM-DD."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if date_from > date_to:
            return Response(
                {"error": {"code": "INVALID_DATE_RANGE", "message": "'from' date cannot be after 'to' date."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_dt = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(date_to, datetime.max.time()))

        # Base event queryset within date range
        events = AnalyticsEvent.objects.filter(
            timestamp__gte=start_dt,
            timestamp__lte=end_dt,
        )

        event_counts = events.aggregate(
            total=Count("id"),
            app_opens=Count("id", filter=Q(event_type=EventType.APP_OPEN)),
            clinic_views=Count("id", filter=Q(event_type=EventType.CLINIC_VIEW)),
            whatsapp_taps=Count("id", filter=Q(event_type=EventType.WHATSAPP_TAP)),
            call_taps=Count("id", filter=Q(event_type=EventType.CALL_TAP)),
            maps_taps=Count("id", filter=Q(event_type=EventType.MAPS_TAP)),
            lead_submits=Count("id", filter=Q(event_type=EventType.LEAD_SUBMITTED)),
        )

        leads_in_range = Lead.objects.filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        )
        total_leads = leads_in_range.count()
        closed_leads = leads_in_range.filter(status=LeadStatus.CLOSED).count()
        contacted_leads = leads_in_range.filter(status=LeadStatus.CONTACTED).count()
        conversion_pct = (
            round((closed_leads / total_leads * 100), 2) if total_leads > 0 else 0.0
        )

        # Clinic engagement breakdown
        clinic_engagement_qs = (
            events.filter(clinic__isnull=False)
            .values("clinic__id", "clinic__name_en")
            .annotate(event_count=Count("id"))
            .order_by("-event_count")[:10]
        )
        clinic_engagement = [
            {
                "clinic_id": str(item["clinic__id"]),
                "clinic_name": item["clinic__name_en"],
                "events_count": item["event_count"],
            }
            for item in clinic_engagement_qs
        ]

        # Daily trends breakdown
        daily_qs = (
            events.values("timestamp__date")
            .annotate(total_events=Count("id"))
            .order_by("timestamp__date")
        )
        daily_trends = [
            {
                "date": str(item["timestamp__date"]),
                "total_events": item["total_events"],
            }
            for item in daily_qs
        ]

        data = {
            "date_from": str(date_from),
            "date_to": str(date_to),
            "total_events": event_counts["total"] or 0,
            "app_opens": event_counts["app_opens"] or 0,
            "clinic_views": event_counts["clinic_views"] or 0,
            "whatsapp_taps": event_counts["whatsapp_taps"] or 0,
            "call_taps": event_counts["call_taps"] or 0,
            "maps_taps": event_counts["maps_taps"] or 0,
            "lead_submissions": total_leads,
            "conversion_metrics": {
                "total_leads": total_leads,
                "contacted_leads": contacted_leads,
                "closed_leads": closed_leads,
                "conversion_percentage": conversion_pct,
            },
            "daily_trends": daily_trends,
            "clinic_engagement": clinic_engagement,
        }
        return Response(data)


class AdminEngagementAnalyticsAPIView(views.APIView):
    """Legacy engagement analytics view."""
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs):
        timeframe = timezone.now() - timedelta(days=30)
        events = AnalyticsEvent.objects.filter(timestamp__gte=timeframe)

        app_opens = events.filter(event_type=EventType.APP_OPEN).count()
        whatsapp_taps = events.filter(event_type=EventType.WHATSAPP_TAP).count()
        call_taps = events.filter(event_type=EventType.CALL_TAP).count()
        maps_taps = events.filter(event_type=EventType.MAPS_TAP).count()
        clinic_views = events.filter(event_type=EventType.CLINIC_VIEW).count()

        total_leads_this_month = Lead.objects.filter(
            created_at__gte=timeframe
        ).count()

        return Response({
            "app_opens_30d": app_opens,
            "whatsapp_taps_30d": whatsapp_taps,
            "call_taps_30d": call_taps,
            "maps_taps_30d": maps_taps,
            "clinic_views_30d": clinic_views,
            "total_leads_30d": total_leads_this_month,
        })


class AdminReferralAnalyticsAPIView(views.APIView):
    """Legacy referral analytics view."""
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs):
        total_successful_invites = ReferralInvite.objects.filter(status="successful").count()
        points_awarded = (
            ReferralPointsLedger.objects.filter(points__gt=0).aggregate(Sum("points"))["points__sum"] or 0
        )
        return Response({
            "total_successful_invites": total_successful_invites,
            "total_points_awarded": points_awarded,
        })


# =====================================================================
# 6. Settings Management
# =====================================================================

class AdminSettingsAPIView(views.APIView):
    """
    Platform Settings management.
    GET /api/v1/admin/settings/
    PUT /api/v1/admin/settings/
    PATCH /api/v1/admin/settings/
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @extend_schema(responses={200: dict})
    def get(self, request, *args, **kwargs):
        settings_qs = PlatformSetting.objects.all().order_by("key")
        serializer = PlatformSettingSerializer(settings_qs, many=True)
        settings_dict = {s.key: s.value for s in settings_qs}
        return Response({
            "settings": serializer.data,
            "config": settings_dict,
        })

    @extend_schema(request=PlatformSettingSerializer, responses={200: PlatformSettingSerializer})
    def put(self, request, *args, **kwargs):
        # Backward compatibility with existing PUT {key, value}
        serializer = PlatformSettingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]
        val = serializer.validated_data["value"]

        if key not in ALLOWED_SETTING_KEYS:
            return Response(
                {"error": {"code": "FORBIDDEN_SETTING", "message": f"Setting key '{key}' cannot be modified."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            setting, _ = PlatformSetting.objects.update_or_create(
                key=key, defaults={"value": val}
            )
            AdminAuditLog.objects.create(
                admin=request.user,
                action_type=AdminActionType.UPDATE_SETTINGS,
                entity_type="PlatformSetting",
                entity_id=None,
                details={"key": key, "value": val},
            )

        return Response(PlatformSettingSerializer(setting).data)

    @extend_schema(request=AdminPlatformSettingUpdateSerializer, responses={200: dict})
    def patch(self, request, *args, **kwargs):
        # Support either {"key": "...", "value": ...} or a map {"setting_key": value}
        if "key" in request.data:
            serializer = AdminPlatformSettingUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            key = serializer.validated_data["key"]
            val = serializer.validated_data["value"]
            updates = {key: val}
        else:
            updates = request.data
            for k in updates.keys():
                if k not in ALLOWED_SETTING_KEYS:
                    return Response(
                        {"error": {"code": "FORBIDDEN_SETTING", "message": f"Setting key '{k}' cannot be modified."}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        updated_settings = []
        with transaction.atomic():
            for k, v in updates.items():
                setting, _ = PlatformSetting.objects.update_or_create(
                    key=k, defaults={"value": v}
                )
                updated_settings.append(setting)
                AdminAuditLog.objects.create(
                    admin=request.user,
                    action_type=AdminActionType.UPDATE_SETTINGS,
                    entity_type="PlatformSetting",
                    entity_id=None,
                    details={"key": k, "value": v},
                )

        return Response({
            "status": "success",
            "updated": PlatformSettingSerializer(updated_settings, many=True).data,
        })


# =====================================================================
# 7. Audit Logging (Read-Only)
# =====================================================================

class AdminAuditLogAPIView(generics.ListAPIView):
    """
    Read-only audit log endpoint.
    GET /api/v1/admin/audit/
    Supports filtering by actor, action_type, entity_type, entity_id, date range.
    """
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]
    serializer_class = AdminAuditLogSerializer
    pagination_class = AdminStandardPagination
    queryset = AdminAuditLog.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AdminAuditLog.objects.none()
        qs = AdminAuditLog.objects.all().select_related("admin").order_by("-created_at")

        actor_param = self.request.query_params.get("actor") or self.request.query_params.get("admin_id")
        if actor_param:
            qs = qs.filter(Q(admin_id=actor_param) | Q(admin__phone=actor_param))

        action_param = self.request.query_params.get("action") or self.request.query_params.get("action_type")
        if action_param:
            qs = qs.filter(action_type__iexact=action_param)

        entity_type_param = self.request.query_params.get("entity_type")
        if entity_type_param:
            qs = qs.filter(entity_type__iexact=entity_type_param)

        entity_id_param = self.request.query_params.get("entity_id")
        if entity_id_param:
            qs = qs.filter(entity_id=entity_id_param)

        date_from = self.request.query_params.get("date_from") or self.request.query_params.get("from")
        if date_from:
            try:
                d = datetime.strptime(date_from, "%Y-%m-%d").date()
                qs = qs.filter(created_at__gte=timezone.make_aware(datetime.combine(d, datetime.min.time())))
            except ValueError:
                pass

        date_to = self.request.query_params.get("date_to") or self.request.query_params.get("to")
        if date_to:
            try:
                d = datetime.strptime(date_to, "%Y-%m-%d").date()
                qs = qs.filter(created_at__lte=timezone.make_aware(datetime.combine(d, datetime.max.time())))
            except ValueError:
                pass

        return qs
