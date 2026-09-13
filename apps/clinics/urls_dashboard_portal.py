from django.urls import path

from apps.clinics.portal_views import ClinicDashboardAPIView

app_name = "clinic_portal_dashboard"

urlpatterns = [
    path("", ClinicDashboardAPIView.as_view(), name="dashboard"),
]
