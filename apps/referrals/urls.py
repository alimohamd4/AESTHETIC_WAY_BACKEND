from django.urls import path
from apps.referrals.views.patient_views import ReferralStatusAPIView, CollectCodeAPIView

app_name = "referrals"

urlpatterns = [
    path("my-status/", ReferralStatusAPIView.as_view(), name="my-status"),
    path("collect-code/", CollectCodeAPIView.as_view(), name="collect-code"),
]
