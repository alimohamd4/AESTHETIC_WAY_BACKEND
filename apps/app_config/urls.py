from django.urls import path
from .views import AppConfigView, SupportInfoView

app_name = "app_config"
urlpatterns = [
    path("config/", AppConfigView.as_view(), name="app-config"),
    path("support-info/", SupportInfoView.as_view(), name="support-info"),
]
