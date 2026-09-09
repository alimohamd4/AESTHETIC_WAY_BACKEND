from django.urls import path
from apps.home.views import HomeFeedAPIView

app_name = "home"

urlpatterns = [
    path("feed/", HomeFeedAPIView.as_view(), name="feed"),
]
