from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.articles.portal_views import ClinicArticlePortalViewSet

app_name = "clinic_portal_articles"

router = DefaultRouter()
router.register("", ClinicArticlePortalViewSet, basename="articles")

urlpatterns = [
    path("", include(router.urls)),
]
