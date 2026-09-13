from django.urls import path

from apps.leads.views.patient_views import (
    LeadCreateAPIView,
    MyLeadDetailAPIView,
    MyLeadsAPIView,
    MyLeadsCountAPIView,
)

app_name = "patient_leads"

urlpatterns = [
    path("", MyLeadsAPIView.as_view(), name="list"),
    path("submit/", LeadCreateAPIView.as_view(), name="submit"),
    path("count/", MyLeadsCountAPIView.as_view(), name="count"),
    path("<uuid:pk>/", MyLeadDetailAPIView.as_view(), name="detail"),
]
