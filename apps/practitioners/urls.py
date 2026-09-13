from django.urls import path

from apps.practitioners.views import (
    PractitionerDetailAPIView,
    PractitionerListAPIView,
)

app_name = "practitioners"

urlpatterns = [
    path("", PractitionerListAPIView.as_view(), name="practitioner-list"),
    path("<str:id>/", PractitionerDetailAPIView.as_view(), name="practitioner-detail"),
]
