from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.offers.portal_views import ClinicOfferPortalViewSet

app_name = "clinic_portal_offers"

router = DefaultRouter()
router.register("", ClinicOfferPortalViewSet, basename="offers")

urlpatterns = [
    path("", include(router.urls)),
]
