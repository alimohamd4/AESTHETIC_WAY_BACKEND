from django.urls import path

from apps.clinics.views import ClinicDetailAPIView, ClinicListAPIView

app_name = "clinics"

urlpatterns = [
    path("", ClinicListAPIView.as_view(), name="clinic-list"),
    path("<str:id>/", ClinicDetailAPIView.as_view(), name="clinic-detail"),
]
