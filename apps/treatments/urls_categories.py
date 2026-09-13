from django.urls import path

from apps.treatments.views import CategoryListAPIView

app_name = "categories"

urlpatterns = [
    path("", CategoryListAPIView.as_view(), name="category-list"),
]
