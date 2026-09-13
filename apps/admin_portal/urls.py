"""
AESTHETIC WAY Backend - Admin Portal URL Routing (Phase 16)
"""
from django.urls import path

from apps.admin_portal.views import (
    AdminArticleModerationViewSet,
    AdminAuditLogAPIView,
    AdminClinicStatusAPIView,
    AdminClinicSubscriptionAPIView,
    AdminClinicViewSet,
    AdminDashboardAPIView,
    AdminEngagementAnalyticsAPIView,
    AdminLeadAPIView,
    AdminLeadDetailAPIView,
    AdminModerationAPIView,
    AdminModerationQueueAPIView,
    AdminOfferModerationViewSet,
    AdminPlatformAnalyticsAPIView,
    AdminProductModerationViewSet,
    AdminReferralAnalyticsAPIView,
    AdminSettingsAPIView,
)

app_name = "admin_portal"

urlpatterns = [
    # Dashboard
    path("dashboard/", AdminDashboardAPIView.as_view(), name="dashboard"),

    # Clinics Management
    path("clinics/", AdminClinicViewSet.as_view({"get": "list"}), name="clinic-list"),
    path(
        "clinics/<uuid:pk>/",
        AdminClinicViewSet.as_view({"get": "retrieve", "patch": "partial_update"}),
        name="clinic-detail",
    ),
    path(
        "clinics/<uuid:pk>/suspend/",
        AdminClinicViewSet.as_view({"post": "suspend"}),
        name="clinic-suspend",
    ),
    path(
        "clinics/<uuid:pk>/activate/",
        AdminClinicViewSet.as_view({"post": "activate"}),
        name="clinic-activate",
    ),
    path(
        "clinics/<uuid:pk>/verify/",
        AdminClinicViewSet.as_view({"post": "verify"}),
        name="clinic-verify",
    ),
    path(
        "clinics/<uuid:pk>/audit/",
        AdminClinicViewSet.as_view({"get": "audit"}),
        name="clinic-audit",
    ),
    # Backward compatibility clinic actions
    path(
        "clinics/<uuid:pk>/status/",
        AdminClinicStatusAPIView.as_view(),
        name="clinic-status",
    ),
    path(
        "clinics/<uuid:pk>/subscription/",
        AdminClinicSubscriptionAPIView.as_view(),
        name="clinic-subscription",
    ),

    # Leads Supervision (Read-Only)
    path("leads/", AdminLeadAPIView.as_view(), name="leads"),
    path("leads/<uuid:pk>/", AdminLeadDetailAPIView.as_view(), name="lead-detail"),

    # Offers Moderation
    path("offers/", AdminOfferModerationViewSet.as_view({"get": "list"}), name="offer-list"),
    path("offers/<uuid:pk>/", AdminOfferModerationViewSet.as_view({"get": "retrieve"}), name="offer-detail"),
    path("offers/<uuid:pk>/moderate/", AdminOfferModerationViewSet.as_view({"post": "moderate"}), name="offer-moderate"),
    path("offers/<uuid:pk>/approve/", AdminOfferModerationViewSet.as_view({"post": "approve"}), name="offer-approve"),
    path("offers/<uuid:pk>/reject/", AdminOfferModerationViewSet.as_view({"post": "reject"}), name="offer-reject"),
    path("offers/<uuid:pk>/suspend/", AdminOfferModerationViewSet.as_view({"post": "suspend"}), name="offer-suspend"),
    path("offers/<uuid:pk>/restore/", AdminOfferModerationViewSet.as_view({"post": "restore"}), name="offer-restore"),

    # Products Moderation
    path("products/", AdminProductModerationViewSet.as_view({"get": "list"}), name="product-list"),
    path("products/<uuid:pk>/", AdminProductModerationViewSet.as_view({"get": "retrieve"}), name="product-detail"),
    path("products/<uuid:pk>/moderate/", AdminProductModerationViewSet.as_view({"post": "moderate"}), name="product-moderate"),
    path("products/<uuid:pk>/approve/", AdminProductModerationViewSet.as_view({"post": "approve"}), name="product-approve"),
    path("products/<uuid:pk>/reject/", AdminProductModerationViewSet.as_view({"post": "reject"}), name="product-reject"),
    path("products/<uuid:pk>/suspend/", AdminProductModerationViewSet.as_view({"post": "suspend"}), name="product-suspend"),
    path("products/<uuid:pk>/restore/", AdminProductModerationViewSet.as_view({"post": "restore"}), name="product-restore"),

    # Articles Moderation
    path("articles/", AdminArticleModerationViewSet.as_view({"get": "list"}), name="article-list"),
    path("articles/<uuid:pk>/", AdminArticleModerationViewSet.as_view({"get": "retrieve"}), name="article-detail"),
    path("articles/<uuid:pk>/moderate/", AdminArticleModerationViewSet.as_view({"post": "moderate"}), name="article-moderate"),
    path("articles/<uuid:pk>/approve/", AdminArticleModerationViewSet.as_view({"post": "approve"}), name="article-approve"),
    path("articles/<uuid:pk>/reject/", AdminArticleModerationViewSet.as_view({"post": "reject"}), name="article-reject"),
    path("articles/<uuid:pk>/suspend/", AdminArticleModerationViewSet.as_view({"post": "suspend"}), name="article-suspend"),
    path("articles/<uuid:pk>/restore/", AdminArticleModerationViewSet.as_view({"post": "restore"}), name="article-restore"),

    # Content Moderation Unified Queue & Legacy Route
    path("moderation/", AdminModerationQueueAPIView.as_view(), name="moderation-queue"),
    path(
        "moderate/<str:model_name>/<uuid:pk>/",
        AdminModerationAPIView.as_view(),
        name="moderate-content",
    ),

    # Platform Analytics
    path("analytics/", AdminPlatformAnalyticsAPIView.as_view(), name="analytics"),
    path(
        "analytics/engagement/",
        AdminEngagementAnalyticsAPIView.as_view(),
        name="analytics-engagement",
    ),
    path(
        "analytics/referrals/",
        AdminReferralAnalyticsAPIView.as_view(),
        name="analytics-referrals",
    ),

    # Settings Management
    path("settings/", AdminSettingsAPIView.as_view(), name="settings"),

    # Audit Logging (Read-Only)
    path("audit/", AdminAuditLogAPIView.as_view(), name="audit"),
]
