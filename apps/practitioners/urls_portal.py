from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.practitioners.portal_views import ClinicPractitionerPortalViewSet

app_name = "clinic_portal_practitioners"

router = DefaultRouter()
router.register("", ClinicPractitionerPortalViewSet, basename="practitioners")

urlpatterns = [
    path("", include(router.urls)),
]
