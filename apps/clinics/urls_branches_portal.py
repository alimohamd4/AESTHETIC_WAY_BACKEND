from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.clinics.portal_views import ClinicBranchPortalViewSet

app_name = "clinic_portal_branches"

router = DefaultRouter()
router.register("", ClinicBranchPortalViewSet, basename="branches")

urlpatterns = [
    path("", include(router.urls)),
]
