from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.products.portal_views import ClinicProductPortalViewSet

app_name = "clinic_portal_products"

router = DefaultRouter()
router.register("", ClinicProductPortalViewSet, basename="products")

urlpatterns = [
    path("", include(router.urls)),
]
