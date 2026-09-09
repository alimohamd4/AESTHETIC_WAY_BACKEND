from django.urls import path
from apps.admin_portal.views import (
    AdminDashboardAPIView, AdminClinicViewSet, AdminClinicStatusAPIView,
    AdminClinicSubscriptionAPIView, AdminLeadAPIView, AdminEngagementAnalyticsAPIView,
    AdminReferralAnalyticsAPIView, AdminSettingsAPIView, AdminModerationAPIView
)

app_name = "admin_portal"

urlpatterns = [
    path("dashboard/", AdminDashboardAPIView.as_view(), name="dashboard"),
    
    path("clinics/", AdminClinicViewSet.as_view({"get": "list"}), name="clinic-list"),
    path("clinics/<uuid:pk>/", AdminClinicViewSet.as_view({"get": "retrieve"}), name="clinic-detail"),
    path("clinics/<uuid:pk>/status/", AdminClinicStatusAPIView.as_view(), name="clinic-status"),
    path("clinics/<uuid:pk>/subscription/", AdminClinicSubscriptionAPIView.as_view(), name="clinic-subscription"),
    
    path("leads/", AdminLeadAPIView.as_view(), name="leads"),
    
    path("analytics/engagement/", AdminEngagementAnalyticsAPIView.as_view(), name="analytics-engagement"),
    path("analytics/referrals/", AdminReferralAnalyticsAPIView.as_view(), name="analytics-referrals"),
    
    path("settings/", AdminSettingsAPIView.as_view(), name="settings"),
    
    path("moderate/<str:model_name>/<uuid:pk>/", AdminModerationAPIView.as_view(), name="moderate-content"),
]
