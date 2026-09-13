from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.treatments.portal_views import ClinicTreatmentPortalViewSet

app_name = "clinic_portal_treatments"

router = DefaultRouter()
router.register("", ClinicTreatmentPortalViewSet, basename="treatments")

urlpatterns = [
    path("", include(router.urls)),
]
