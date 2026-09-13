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
    path("patient/leads/", include("apps.leads.urls_patient", namespace="patient_leads")),
    path("clinic-portal/leads/", include("apps.leads.urls_clinic", namespace="clinic_leads")),
    path("referral/", include("apps.referrals.urls", namespace="referrals")),
    path("clinic-portal/discount-codes/", include("apps.referrals.urls_clinic", namespace="clinic_referrals")),
    path("analytics/", include("apps.analytics.urls", namespace="analytics")),
    path("clinic-portal/analytics/", include("apps.analytics.urls_clinic", namespace="clinic_analytics")),
    # Clinic Portal Management (Phase 14)
    path("clinic-portal/dashboard/", include("apps.clinics.urls_dashboard_portal", namespace="clinic_portal_dashboard")),
    path("clinic-portal/profile/", include("apps.clinics.urls_profile_portal", namespace="clinic_portal_profile")),
    path("clinic-portal/branches/", include("apps.clinics.urls_branches_portal", namespace="clinic_portal_branches")),
    path("clinic-portal/practitioners/", include("apps.practitioners.urls_portal", namespace="clinic_portal_practitioners")),
    path("clinic-portal/treatments/", include("apps.treatments.urls_portal", namespace="clinic_portal_treatments")),
    path("clinic-portal/offers/", include("apps.offers.urls_portal", namespace="clinic_portal_offers")),
    path("clinic-portal/products/", include("apps.products.urls_portal", namespace="clinic_portal_products")),
    path("clinic-portal/articles/", include("apps.articles.urls_portal", namespace="clinic_portal_articles")),
    path("media/", include("apps.media.urls", namespace="media")),
    path("health/", include("core.health.urls", namespace="health")),
    # Discovery & Catalog Public APIs (Phase 13)
    path("categories/", include("apps.treatments.urls_categories", namespace="categories")),
    path("clinics/", include("apps.clinics.urls", namespace="clinics")),
    path("practitioners/", include("apps.practitioners.urls", namespace="practitioners")),
    path("treatments/", include("apps.treatments.urls", namespace="treatments")),
    path("offers/", include("apps.offers.urls", namespace="offers")),
    path("products/", include("apps.products.urls", namespace="products")),
    path("articles/", include("apps.articles.urls", namespace="articles")),
]
