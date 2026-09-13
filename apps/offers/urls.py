from django.urls import path

from apps.offers.views import OfferDetailAPIView, OfferListAPIView

app_name = "offers"

urlpatterns = [
    path("", OfferListAPIView.as_view(), name="offer-list"),
    path("<str:id>/", OfferDetailAPIView.as_view(), name="offer-detail"),
]
