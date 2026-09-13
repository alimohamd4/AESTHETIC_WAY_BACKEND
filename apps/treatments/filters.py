import django_filters

from apps.treatments.models import Treatment


class TreatmentFilter(django_filters.FilterSet):
    category = django_filters.UUIDFilter(field_name="category_id")
    category_id = django_filters.UUIDFilter(field_name="category_id")
    clinic = django_filters.UUIDFilter(field_name="clinic_id")
    clinic_id = django_filters.UUIDFilter(field_name="clinic_id")
    practitioner = django_filters.UUIDFilter(method="filter_practitioner")
    practitioner_id = django_filters.UUIDFilter(method="filter_practitioner")

    class Meta:
        model = Treatment
        fields = ["category", "category_id", "clinic", "clinic_id", "practitioner", "practitioner_id"]

    def filter_practitioner(self, queryset, name, value):
        if value:
            return queryset.filter(
                practitioners__id=value,
                practitioners__status="active",
                practitioners__deleted_at__isnull=True,
            ).distinct()
        return queryset
