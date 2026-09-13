from rest_framework import serializers

from apps.articles.models import Article
from apps.clinics.models import Clinic
from apps.practitioners.models import Practitioner


class PublicArticleClinicSummarySerializer(serializers.ModelSerializer):
    """Public clinic summary for article responses."""

    class Meta:
        model = Clinic
        fields = [
            "id",
            "name_en",
            "name_ar",
            "slug",
            "city",
            "logo",
        ]
        read_only_fields = fields


class PublicArticleAuthorSummarySerializer(serializers.ModelSerializer):
    """Public practitioner summary authoring an article."""

    avatar_url = serializers.CharField(read_only=True)

    class Meta:
        model = Practitioner
        fields = [
            "id",
            "name_en",
            "name_ar",
            "title_en",
            "title_ar",
            "type",
            "avatar_url",
        ]
        read_only_fields = fields


class PublicArticleListSerializer(serializers.ModelSerializer):
    """
    Public listing serializer for published articles.
    """

    clinic = PublicArticleClinicSummarySerializer(read_only=True)
    author_practitioner = PublicArticleAuthorSummarySerializer(read_only=True)
    cover_image_url = serializers.CharField(source="image_url", read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title_en",
            "title_ar",
            "slug",
            "content_en",
            "content_ar",
            "cover_image_url",
            "published_at",
            "created_at",
            "clinic",
            "author_practitioner",
        ]
        read_only_fields = fields


class PublicArticleDetailSerializer(serializers.ModelSerializer):
    """
    Public detail serializer for a single published article.
    """

    clinic = PublicArticleClinicSummarySerializer(read_only=True)
    author_practitioner = PublicArticleAuthorSummarySerializer(read_only=True)
    cover_image_url = serializers.CharField(source="image_url", read_only=True)

    class Meta:
        model = Article
        fields = [
            "id",
            "title_en",
            "title_ar",
            "slug",
            "content_en",
            "content_ar",
            "cover_image_url",
            "published_at",
            "created_at",
            "clinic",
            "author_practitioner",
        ]
        read_only_fields = fields
