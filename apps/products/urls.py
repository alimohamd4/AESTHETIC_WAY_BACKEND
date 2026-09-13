from django.urls import path

from apps.products.views import ProductDetailAPIView, ProductListAPIView

app_name = "products"

urlpatterns = [
    path("", ProductListAPIView.as_view(), name="product-list"),
    path("<str:id>/", ProductDetailAPIView.as_view(), name="product-detail"),
]
