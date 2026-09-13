from django.urls import path

from apps.clinics.portal_views import ClinicProfileAPIView

app_name = "clinic_portal_profile"

urlpatterns = [
    path("", ClinicProfileAPIView.as_view(), name="profile"),
]
