from django.urls import path

from apps.treatments.views import TreatmentDetailAPIView, TreatmentListAPIView

app_name = "treatments"

urlpatterns = [
    path("", TreatmentListAPIView.as_view(), name="treatment-list"),
    path("<str:id>/", TreatmentDetailAPIView.as_view(), name="treatment-detail"),
]
