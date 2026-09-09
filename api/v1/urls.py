"""
AESTHETIC WAY Backend - API v1 URL Router
"""
from django.urls import include, path

app_name = "api_v1"

urlpatterns = [
    path("auth/", include("apps.accounts.urls", namespace="auth")),
    path("admin/", include("apps.admin_portal.urls", namespace="admin")),
    path("app/", include("apps.app_config.urls", namespace="app_config")),
    path("home/", include("apps.home.urls", namespace="home")),
    path("leads/", include("apps.leads.urls", namespace="leads")),
    path("clinic-portal/leads/", include("apps.leads.urls_clinic", namespace="clinic_leads")),
    path("referral/", include("apps.referrals.urls", namespace="referrals")),
    path("clinic-portal/discount-codes/", include("apps.referrals.urls_clinic", namespace="clinic_referrals")),
    path("analytics/", include("apps.analytics.urls", namespace="analytics")),
    path("clinic-portal/analytics/", include("apps.analytics.urls_clinic", namespace="clinic_analytics")),
    path("media/", include("apps.media.urls", namespace="media")),
    path("health/", include("core.health.urls", namespace="health")),
]
