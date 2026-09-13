import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ClinicRoleInClinic, ClinicUser, UserRole
from apps.articles.models import Article, ContentStatus
from apps.clinics.models import Clinic, ClinicStatus
from apps.practitioners.models import Practitioner, PractitionerType

User = get_user_model()


@pytest.mark.django_db
class TestClinicPortalArticles:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:clinic_portal_articles:articles-list")

        self.clinic_a = Clinic.objects.create(name_en="Clinic Alpha", status=ClinicStatus.ACTIVE)
        self.clinic_b = Clinic.objects.create(name_en="Clinic Beta", status=ClinicStatus.ACTIVE)

        self.staff_a = User.objects.create_user(phone="+971501111111", full_name="Staff A", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_a, clinic=self.clinic_a, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.staff_b = User.objects.create_user(phone="+971502222222", full_name="Staff B", role=UserRole.CLINIC_STAFF)
        ClinicUser.objects.create(user=self.staff_b, clinic=self.clinic_b, role_in_clinic=ClinicRoleInClinic.STAFF)

        self.doc_a = Practitioner.objects.create(
            clinic=self.clinic_a,
            name_en="Dr. Alpha Author",
            type=PractitionerType.DOCTOR,
            status="active",
        )
        self.doc_b = Practitioner.objects.create(
            clinic=self.clinic_b,
            name_en="Dr. Beta Author",
            type=PractitionerType.DOCTOR,
            status="active",
        )

        # Article A
        self.article_a = Article.objects.create(
            clinic=self.clinic_a,
            author_practitioner=self.doc_a,
            title_en="Alpha Post-Care Advice",
            content_en="Instructions following facial treatments.",
            slug="alpha-post-care-advice",
            is_published=True,
            status=ContentStatus.ACTIVE,
        )

        # Article B
        self.article_b = Article.objects.create(
            clinic=self.clinic_b,
            author_practitioner=self.doc_b,
            title_en="Beta Laser Guide",
            content_en="Everything about laser treatments.",
            slug="beta-laser-guide",
            is_published=True,
            status=ContentStatus.ACTIVE,
        )

        # Platform Article (clinic=None)
        self.article_platform = Article.objects.create(
            clinic=None,
            title_en="Platform Aesthetic Trends",
            content_en="Global trends in cosmetic medicine.",
            slug="platform-aesthetic-trends",
            is_published=True,
            status=ContentStatus.ACTIVE,
        )

    def test_list_articles_scoped_to_clinic_excludes_platform_and_other_clinics(self):
        self.client.force_authenticate(user=self.staff_a)
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["id"] == str(self.article_a.id)

    def test_create_article_with_same_clinic_author_success(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "title_en": "Skincare Essentials",
            "title_ar": "أساسيات العناية بالبشرة",
            "content_en": "Guide written by Dr. Alpha.",
            "author_practitioner": str(self.doc_a.id),
            "is_published": True,
            "status": "active",
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_201_CREATED
        new_id = response.json()["id"]

        article = Article.objects.get(id=new_id)
        assert article.clinic == self.clinic_a
        assert article.author_practitioner == self.doc_a
        assert article.slug == "skincare-essentials"
        assert article.published_at is not None

    def test_create_article_with_other_clinic_author_rejected(self):
        self.client.force_authenticate(user=self.staff_a)
        payload = {
            "title_en": "Cross Clinic Article",
            "content_en": "Invalid author assignment.",
            # Author from Clinic B
            "author_practitioner": str(self.doc_b.id),
        }
        response = self.client.post(self.list_url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "author_practitioner" in str(response.json())

    def test_retrieve_article_detail(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_articles:articles-detail", kwargs={"pk": str(self.article_a.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["title_en"] == "Alpha Post-Care Advice"

    def test_update_article(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_articles:articles-detail", kwargs={"pk": str(self.article_a.id)})
        response = self.client.patch(url, {"content_en": "Updated advice details."})
        assert response.status_code == status.HTTP_200_OK
        self.article_a.refresh_from_db()
        assert self.article_a.content_en == "Updated advice details."

    def test_delete_article_soft_deletes(self):
        self.client.force_authenticate(user=self.staff_a)
        url = reverse("api_v1:clinic_portal_articles:articles-detail", kwargs={"pk": str(self.article_a.id)})
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.article_a.refresh_from_db()
        assert self.article_a.deleted_at is not None
        assert self.article_a.is_published is False

        res_list = self.client.get(self.list_url)
        assert len(res_list.json()["results"]) == 0

    def test_cannot_access_platform_article(self):
        self.client.force_authenticate(user=self.staff_a)
        url_platform = reverse("api_v1:clinic_portal_articles:articles-detail", kwargs={"pk": str(self.article_platform.id)})
        assert self.client.get(url_platform).status_code == status.HTTP_404_NOT_FOUND

    def test_anti_idor_cross_clinic_access_returns_404(self):
        self.client.force_authenticate(user=self.staff_a)
        url_b = reverse("api_v1:clinic_portal_articles:articles-detail", kwargs={"pk": str(self.article_b.id)})

        assert self.client.get(url_b).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.patch(url_b, {"title_en": "Defaced"}).status_code == status.HTTP_404_NOT_FOUND
        assert self.client.delete(url_b).status_code == status.HTTP_404_NOT_FOUND

        self.article_b.refresh_from_db()
        assert self.article_b.title_en == "Beta Laser Guide"
        assert self.article_b.deleted_at is None
