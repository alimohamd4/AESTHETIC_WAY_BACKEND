from django.utils import timezone
from rest_framework import filters, viewsets

from apps.articles.models import Article
from apps.articles.portal_serializers import ClinicArticlePortalSerializer
from apps.clinics.portal_permissions import IsClinicPortalAccess, get_user_clinic


class ClinicArticlePortalViewSet(viewsets.ModelViewSet):
    """
    Clinic portal CRUD for educational articles.
    Strictly scoped to the authenticated clinic.
    """
    permission_classes = [IsClinicPortalAccess]
    serializer_class = ClinicArticlePortalSerializer
    queryset = Article.objects.none()
    filter_backends = [filters.SearchFilter]
    search_fields = ["title_en", "title_ar", "content_en", "content_ar"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not (
            self.request.user and self.request.user.is_authenticated
        ):
            return Article.objects.none()

        clinic = get_user_clinic(self.request.user)
        return Article.objects.filter(
            clinic=clinic,
            deleted_at__isnull=True,
        ).select_related("author_practitioner").order_by("-created_at")

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.is_published = False
        instance.save(update_fields=["deleted_at", "is_published"])
