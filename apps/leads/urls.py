from django.urls import path
from apps.leads.views.patient_views import (
    LeadCreateAPIView,
    MyLeadsAPIView,
    MyLeadsCountAPIView
)

app_name = "leads"

urlpatterns = [
    path("", LeadCreateAPIView.as_view(), name="create"),
    path("my/", MyLeadsAPIView.as_view(), name="my"),
    path("my/count/", MyLeadsCountAPIView.as_view(), name="my-count"),
]
