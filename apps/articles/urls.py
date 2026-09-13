from django.urls import path

from apps.articles.views import ArticleDetailAPIView, ArticleListAPIView

app_name = "articles"

urlpatterns = [
    path("", ArticleListAPIView.as_view(), name="article-list"),
    path("<str:id>/", ArticleDetailAPIView.as_view(), name="article-detail"),
]
