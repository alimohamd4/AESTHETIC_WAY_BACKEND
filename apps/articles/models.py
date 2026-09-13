import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class ContentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    REJECTED = "rejected", "Rejected"


class Article(models.Model):
    """
    Educational and aesthetic content.
    Can be authored by a clinic practitioner or platform-level (clinic=None).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic = models.ForeignKey(
        "clinics.Clinic",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="articles",
    )
    author_practitioner = models.ForeignKey(
        "practitioners.Practitioner",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )

    # Bilingual identity
    title_en = models.CharField(max_length=255, db_index=True)
    title_ar = models.CharField(max_length=255, blank=True, default="", db_index=True)
    slug = models.SlugField(max_length=280, unique=True, blank=True)

    # Bilingual body content
    content_en = models.TextField(blank=True, default="")
    content_ar = models.TextField(blank=True, default="")

    # Media integration
    cover_image = models.URLField(blank=True, default="")
    media_asset = models.ForeignKey(
        "media.MediaAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
    )

    # Publishing & Moderation status
    status = models.CharField(
        max_length=20,
        choices=ContentStatus.choices,
        default=ContentStatus.ACTIVE,
        db_index=True,
    )
    is_published = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # Timestamps & soft-delete
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "articles"
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["clinic", "status", "is_published"]),
            models.Index(fields=["is_published", "published_at"]),
        ]

    def __str__(self):
        return self.title_en

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title_en) or f"article-{str(self.id)[:8]}"
            slug = base_slug
            n = 1
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def image_url(self) -> str:
        if self.cover_image:
            return self.cover_image
        if self.media_asset:
            return self.media_asset.url
        return ""
