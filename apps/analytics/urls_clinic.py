from django.urls import path

from apps.analytics.views import ClinicAnalyticsAPIView

app_name = "clinic_analytics"

urlpatterns = [
    path("", ClinicAnalyticsAPIView.as_view(), name="dashboard"),
]
