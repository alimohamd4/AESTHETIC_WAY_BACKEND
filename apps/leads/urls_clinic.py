from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.leads.views.clinic_views import ClinicLeadViewSet

app_name = "clinic_leads"

router = DefaultRouter()
router.register("", ClinicLeadViewSet, basename="clinic-leads")

urlpatterns = [
    path("", include(router.urls)),
]
