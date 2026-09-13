import uuid

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.articles.filters import ArticleFilter
from apps.articles.models import Article, ContentStatus
from apps.articles.serializers import (
    PublicArticleDetailSerializer,
    PublicArticleListSerializer,
)
from apps.clinics.models import ClinicStatus
from apps.practitioners.models import PractitionerStatus


class ArticleListAPIView(generics.ListAPIView):
    """
    Public endpoint to discover published educational articles.
    Only returns active, published, non-deleted articles whose clinic/practitioner are active.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicArticleListSerializer
    filterset_class = ArticleFilter
    search_fields = ["title_en", "title_ar", "content_en", "content_ar"]
    ordering_fields = ["published_at", "created_at"]
    ordering = ["-published_at", "-created_at"]

    def get_queryset(self):
        now = timezone.now()
        return Article.objects.filter(
            is_published=True,
            status=ContentStatus.ACTIVE,
            deleted_at__isnull=True,
        ).filter(
            Q(published_at__isnull=True) | Q(published_at__lte=now)
        ).filter(
            Q(clinic__isnull=True) | Q(clinic__status=ClinicStatus.ACTIVE, clinic__deleted_at__isnull=True)
        ).filter(
            Q(author_practitioner__isnull=True) | Q(author_practitioner__status=PractitionerStatus.ACTIVE, author_practitioner__deleted_at__isnull=True)
        ).select_related("clinic", "author_practitioner", "media_asset")


class ArticleDetailAPIView(generics.RetrieveAPIView):
    """
    Public endpoint to view article details.
    Supports lookup by UUID primary key or unique slug.
    """
    permission_classes = [AllowAny]
    serializer_class = PublicArticleDetailSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        now = timezone.now()
        return Article.objects.filter(
            is_published=True,
            status=ContentStatus.ACTIVE,
            deleted_at__isnull=True,
        ).filter(
            Q(published_at__isnull=True) | Q(published_at__lte=now)
        ).filter(
            Q(clinic__isnull=True) | Q(clinic__status=ClinicStatus.ACTIVE, clinic__deleted_at__isnull=True)
        ).filter(
            Q(author_practitioner__isnull=True) | Q(author_practitioner__status=PractitionerStatus.ACTIVE, author_practitioner__deleted_at__isnull=True)
        ).select_related("clinic", "author_practitioner", "media_asset")

    def get_object(self):
        lookup = self.kwargs.get(self.lookup_url_kwarg)
        try:
            val = uuid.UUID(str(lookup))
            return get_object_or_404(self.get_queryset(), pk=val)
        except (ValueError, TypeError):
            return get_object_or_404(self.get_queryset(), slug=lookup)
