import django_filters

from apps.articles.models import Article


class ArticleFilter(django_filters.FilterSet):
    clinic = django_filters.UUIDFilter(field_name="clinic_id")
    clinic_id = django_filters.UUIDFilter(field_name="clinic_id")
    practitioner = django_filters.UUIDFilter(field_name="author_practitioner_id")
    practitioner_id = django_filters.UUIDFilter(field_name="author_practitioner_id")
    author_practitioner = django_filters.UUIDFilter(field_name="author_practitioner_id")

    class Meta:
        model = Article
        fields = ["clinic", "clinic_id", "practitioner", "practitioner_id", "author_practitioner"]
