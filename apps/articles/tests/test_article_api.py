import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.articles.models import Article, ContentStatus
from apps.clinics.models import Clinic, ClinicStatus
from apps.practitioners.models import (
    Practitioner,
    PractitionerStatus,
    PractitionerType,
)


@pytest.mark.django_db
class TestArticleAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:articles:article-list")

        self.clinic_active = Clinic.objects.create(
            name_en="Aesthetic Clinic",
            status=ClinicStatus.ACTIVE,
            city="Dubai",
        )
        self.clinic_suspended = Clinic.objects.create(
            name_en="Suspended Clinic",
            status=ClinicStatus.SUSPENDED,
            city="Dubai",
        )

        self.doctor = Practitioner.objects.create(
            clinic=self.clinic_active,
            name_en="Dr. Layla",
            type=PractitionerType.DOCTOR,
            status=PractitionerStatus.ACTIVE,
        )
        self.doctor_inactive = Practitioner.objects.create(
            clinic=self.clinic_active,
            name_en="Dr. Inactive",
            type=PractitionerType.DOCTOR,
            status=PractitionerStatus.INACTIVE,
        )

        now = timezone.now()

        # Published clinic article
        self.article_clinic = Article.objects.create(
            clinic=self.clinic_active,
            author_practitioner=self.doctor,
            title_en="Benefits of Hyaluronic Acid",
            title_ar="فوائد حمض الهيالورونيك",
            content_en="Comprehensive guide to skin hydration and rejuvenation.",
            slug="benefits-of-hyaluronic-acid",
            cover_image="https://example.com/article1.jpg",
            is_published=True,
            published_at=now - timezone.timedelta(days=2),
            status=ContentStatus.ACTIVE,
        )

        # Published platform article (clinic=None)
        self.article_platform = Article.objects.create(
            clinic=None,
            author_practitioner=None,
            title_en="How to Prepare for Laser Treatments",
            slug="how-to-prepare-for-laser-treatments",
            content_en="Essential tips before your laser session.",
            is_published=True,
            published_at=now - timezone.timedelta(days=5),
            status=ContentStatus.ACTIVE,
        )

        # Unpublished article (draft)
        self.article_draft = Article.objects.create(
            clinic=self.clinic_active,
            title_en="Draft Article Not Yet Published",
            slug="draft-article",
            is_published=False,
            status=ContentStatus.ACTIVE,
        )

        # Future dated article
        self.article_future = Article.objects.create(
            clinic=self.clinic_active,
            title_en="Future Article Embargoed",
            slug="future-article",
            is_published=True,
            published_at=now + timezone.timedelta(days=7),
            status=ContentStatus.ACTIVE,
        )

        # Soft-deleted article
        self.article_deleted = Article.objects.create(
            clinic=self.clinic_active,
            title_en="Soft Deleted Article",
            slug="deleted-article",
            is_published=True,
            published_at=now - timezone.timedelta(days=1),
            deleted_at=now,
            status=ContentStatus.ACTIVE,
        )

        # Article from suspended clinic
        self.article_suspended_clinic = Article.objects.create(
            clinic=self.clinic_suspended,
            title_en="Suspended Clinic Article",
            slug="suspended-clinic-article",
            is_published=True,
            published_at=now - timezone.timedelta(days=1),
            status=ContentStatus.ACTIVE,
        )

        # Article from inactive author
        self.article_inactive_author = Article.objects.create(
            clinic=self.clinic_active,
            author_practitioner=self.doctor_inactive,
            title_en="Article by Inactive Practitioner",
            slug="inactive-author-article",
            is_published=True,
            published_at=now - timezone.timedelta(days=1),
            status=ContentStatus.ACTIVE,
        )

    def test_public_articles_list_published_only(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        titles = [a["title_en"] for a in response.json()["results"]]
        assert "Benefits of Hyaluronic Acid" in titles
        assert "How to Prepare for Laser Treatments" in titles
        assert "Draft Article Not Yet Published" not in titles
        assert "Future Article Embargoed" not in titles
        assert "Soft Deleted Article" not in titles
        assert "Suspended Clinic Article" not in titles
        assert "Article by Inactive Practitioner" not in titles

    def test_clinic_filtering(self):
        response = self.client.get(self.list_url, {"clinic_id": str(self.clinic_active.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["title_en"] == "Benefits of Hyaluronic Acid"

    def test_practitioner_filtering(self):
        response = self.client.get(self.list_url, {"practitioner_id": str(self.doctor.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["title_en"] == "Benefits of Hyaluronic Acid"

    def test_search_articles(self):
        response = self.client.get(self.list_url, {"search": "Laser"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["title_en"] == "How to Prepare for Laser Treatments"

    def test_article_detail_by_id_and_slug(self):
        # By UUID
        url_id = reverse("api_v1:articles:article-detail", kwargs={"id": str(self.article_clinic.id)})
        res_id = self.client.get(url_id)
        assert res_id.status_code == status.HTTP_200_OK
        data = res_id.json()
        assert data["title_en"] == "Benefits of Hyaluronic Acid"
        assert data["clinic"]["name_en"] == "Aesthetic Clinic"
        assert data["author_practitioner"]["name_en"] == "Dr. Layla"
        assert data["cover_image_url"] == "https://example.com/article1.jpg"

        # By slug
        url_slug = reverse("api_v1:articles:article-detail", kwargs={"id": self.article_clinic.slug})
        res_slug = self.client.get(url_slug)
        assert res_slug.status_code == status.HTTP_200_OK
        assert res_slug.json()["id"] == str(self.article_clinic.id)

    def test_platform_article_detail_nullable_clinic(self):
        url = reverse("api_v1:articles:article-detail", kwargs={"id": self.article_platform.slug})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["clinic"] is None
        assert data["author_practitioner"] is None

    def test_unpublished_or_deleted_article_detail_returns_404(self):
        url_draft = reverse("api_v1:articles:article-detail", kwargs={"id": str(self.article_draft.id)})
        assert self.client.get(url_draft).status_code == status.HTTP_404_NOT_FOUND

        url_deleted = reverse("api_v1:articles:article-detail", kwargs={"id": str(self.article_deleted.id)})
        assert self.client.get(url_deleted).status_code == status.HTTP_404_NOT_FOUND

    def test_private_fields_not_exposed(self):
        response = self.client.get(self.list_url)
        item = response.json()["results"][0]
        assert "status" not in item
        assert "deleted_at" not in item
        assert "is_published" not in item
