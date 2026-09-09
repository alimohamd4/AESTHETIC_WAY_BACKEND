from rest_framework import views, viewsets, generics, status
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404

from apps.accounts.models import User, UserRole, PatientProfile
from apps.clinics.models import Clinic
from apps.leads.models import Lead
from apps.leads.serializers import ClinicLeadSerializer
from apps.offers.models import Offer
from apps.products.models import Product
from apps.articles.models import Article
from apps.referrals.models import ReferralInvite, ReferralPointsLedger

from apps.admin_portal.permissions import IsSuperAdmin
from apps.admin_portal.models import AdminAuditLog, AdminActionType
from apps.admin_portal.serializers import (
    AdminClinicSerializer, ClinicStatusUpdateSerializer, ClinicSubscriptionUpdateSerializer,
    PlatformSettingSerializer, ContentModerationSerializer
)
from apps.app_config.models import PlatformSetting


class AdminDashboardAPIView(views.APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request, *args, **kwargs):
        total_patients = User.objects.filter(role=UserRole.PATIENT).count()
        total_clinics = Clinic.objects.count()
        total_leads = Lead.objects.count()
        
        return Response({
            "total_patients": total_patients,
            "total_clinics": total_clinics,
            "total_leads": total_leads,
        })


class AdminClinicViewSet(viewsets.ModelViewSet):
    """
    Admin management of clinics.
    """
    permission_classes = [IsSuperAdmin]
    serializer_class = AdminClinicSerializer
    queryset = Clinic.objects.all().order_by("-created_at")
    http_method_names = ['get', 'patch']


class AdminClinicStatusAPIView(views.APIView):
    permission_classes = [IsSuperAdmin]
    
    def patch(self, request, pk, *args, **kwargs):
        clinic = get_object_or_404(Clinic, pk=pk)
        serializer = ClinicStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        old_status = clinic.status
        new_status = serializer.validated_data["status"]
        
        clinic.status = new_status
        clinic.moderation_notes = serializer.validated_data.get("moderation_notes", clinic.moderation_notes)
        clinic.moderated_by = request.user
        clinic.moderated_at = timezone.now()
        clinic.save(update_fields=["status", "moderation_notes", "moderated_by", "moderated_at"])
        
        # Log audit
        AdminAuditLog.objects.create(
            admin=request.user,
            action_type=AdminActionType.SUSPEND_CLINIC if new_status == "suspended" else AdminActionType.UPDATE_SETTINGS,
            entity_type="Clinic",
            entity_id=clinic.id,
            details={"old_status": old_status, "new_status": new_status}
        )
        
        return Response({"status": "success", "new_status": clinic.status})


class AdminClinicSubscriptionAPIView(views.APIView):
    permission_classes = [IsSuperAdmin]
    
    def patch(self, request, pk, *args, **kwargs):
        clinic = get_object_or_404(Clinic, pk=pk)
        serializer = ClinicSubscriptionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        old_tier = clinic.subscription_tier
        new_tier = serializer.validated_data["subscription_tier"]
        
        clinic.subscription_tier = new_tier
        clinic.save(update_fields=["subscription_tier"])
        
        # Log audit
        AdminAuditLog.objects.create(
            admin=request.user,
            action_type=AdminActionType.UPDATE_SUBSCRIPTION,
            entity_type="Clinic",
            entity_id=clinic.id,
            details={"old_tier": old_tier, "new_tier": new_tier}
        )
        
        return Response({"status": "success", "new_tier": clinic.subscription_tier})


class AdminLeadAPIView(generics.ListAPIView):
    """
    Read-only view of leads for Super Admin.
    """
    permission_classes = [IsSuperAdmin]
    serializer_class = ClinicLeadSerializer
    queryset = Lead.objects.all().order_by("-created_at")


class AdminEngagementAnalyticsAPIView(views.APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request, *args, **kwargs):
        timeframe = timezone.now() - timedelta(days=30)
        from apps.analytics.models import AnalyticsEvent, EventType
        
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
            "total_leads_30d": total_leads_this_month
        })


class AdminReferralAnalyticsAPIView(views.APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request, *args, **kwargs):
        total_successful_invites = ReferralInvite.objects.filter(status="successful").count()
        points_awarded = ReferralPointsLedger.objects.filter(points__gt=0).aggregate(Sum("points"))["points__sum"] or 0
        return Response({
            "total_successful_invites": total_successful_invites,
            "total_points_awarded": points_awarded
        })


class AdminSettingsAPIView(views.APIView):
    permission_classes = [IsSuperAdmin]
    
    def get(self, request, *args, **kwargs):
        settings_qs = PlatformSetting.objects.all()
        serializer = PlatformSettingSerializer(settings_qs, many=True)
        return Response(serializer.data)
        
    def put(self, request, *args, **kwargs):
        serializer = PlatformSettingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        key = serializer.validated_data["key"]
        val = serializer.validated_data["value"]
        
        setting, created = PlatformSetting.objects.update_or_create(
            key=key, defaults={"value": val}
        )
        
        # Log audit
        AdminAuditLog.objects.create(
            admin=request.user,
            action_type=AdminActionType.UPDATE_SETTINGS,
            entity_type="PlatformSetting",
            entity_id=None,
            details={"key": key, "value": val}
        )
        
        return Response(PlatformSettingSerializer(setting).data)


class AdminModerationAPIView(views.APIView):
    permission_classes = [IsSuperAdmin]
    
    def get_model(self, model_name):
        models = {
            "offer": Offer,
            "product": Product,
            "article": Article
        }
        return models.get(model_name.lower())
        
    def patch(self, request, model_name, pk, *args, **kwargs):
        ModelClass = self.get_model(model_name)
        if not ModelClass:
            return Response({"detail": "Invalid model type."}, status=status.HTTP_400_BAD_REQUEST)
            
        instance = get_object_or_404(ModelClass, pk=pk)
        
        serializer = ContentModerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        old_status = getattr(instance, "status", None)
        new_status = serializer.validated_data["status"]
        
        instance.status = new_status
        instance.save(update_fields=["status"])
        
        # Log audit
        AdminAuditLog.objects.create(
            admin=request.user,
            action_type=AdminActionType.MODERATE_CONTENT,
            entity_type=ModelClass.__name__,
            entity_id=instance.id,
            details={"old_status": old_status, "new_status": new_status}
        )
        
        return Response({"status": "success", "new_status": new_status})
