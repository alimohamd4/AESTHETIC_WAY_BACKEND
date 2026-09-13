from django.urls import path

from apps.analytics.views import EventIngestionAPIView

app_name = "analytics"

urlpatterns = [
    path("events/", EventIngestionAPIView.as_view(), name="events"),
]
