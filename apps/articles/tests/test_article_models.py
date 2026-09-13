from django.test import TestCase
from django.utils import timezone

from apps.articles.models import Article, ContentStatus
from apps.clinics.models import Clinic
from apps.practitioners.models import Practitioner, PractitionerType


class ArticleModelTests(TestCase):
    def setUp(self):
        self.clinic = Clinic.objects.create(name_en="Aesthetic Clinic", city="Dubai")
        self.practitioner = Practitioner.objects.create(
            clinic=self.clinic,
            name_en="Dr. Layla",
            type=PractitionerType.DOCTOR,
        )

    def test_article_with_clinic_and_practitioner(self):
        """Article can be affiliated with a clinic and an author practitioner."""
        article = Article.objects.create(
            clinic=self.clinic,
            author_practitioner=self.practitioner,
            title_en="Benefits of Laser Facials",
            title_ar="فوائد ليزر الوجه",
            content_en="Detailed explanation...",
            content_ar="شرح مفصل...",
            is_published=True,
            published_at=timezone.now(),
        )
        self.assertEqual(article.clinic, self.clinic)
        self.assertEqual(article.author_practitioner, self.practitioner)
        self.assertTrue(article.slug.startswith("benefits-of-laser-facials"))

    def test_platform_article_nullable_clinic(self):
        """Platform-wide articles can have clinic=None and author_practitioner=None."""
        article = Article.objects.create(
            clinic=None,
            author_practitioner=None,
            title_en="Skincare Trends 2026",
            status=ContentStatus.ACTIVE,
        )
        self.assertIsNone(article.clinic)
        self.assertIsNone(article.author_practitioner)
        self.assertEqual(article.slug, "skincare-trends-2026")

    def test_slug_uniqueness_auto_increment(self):
        """Duplicate titles generate distinct auto-incremented slugs."""
        a1 = Article.objects.create(title_en="Botox Myths")
        a2 = Article.objects.create(title_en="Botox Myths")
        self.assertEqual(a1.slug, "botox-myths")
        self.assertEqual(a2.slug, "botox-myths-1")

    def test_publication_state(self):
        """Unpublished article reflects publication state."""
        article = Article.objects.create(
            title_en="Draft Article",
            is_published=False,
            published_at=None,
        )
        self.assertFalse(article.is_published)
        self.assertIsNone(article.published_at)
