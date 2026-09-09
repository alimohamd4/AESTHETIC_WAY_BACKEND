from django.urls import path
from apps.referrals.views.clinic_views import VerifyDiscountCodeAPIView, RedeemDiscountCodeAPIView

app_name = "clinic_referrals"

urlpatterns = [
    path("verify/", VerifyDiscountCodeAPIView.as_view(), name="verify"),
    path("redeem/", RedeemDiscountCodeAPIView.as_view(), name="redeem"),
]
