import django_filters

from apps.practitioners.models import Practitioner, PractitionerType


class PractitionerFilter(django_filters.FilterSet):
    clinic = django_filters.UUIDFilter(field_name="clinic_id")
    clinic_id = django_filters.UUIDFilter(field_name="clinic_id")
    type = django_filters.ChoiceFilter(choices=PractitionerType.choices)
    treatment = django_filters.UUIDFilter(method="filter_treatment")
    treatment_id = django_filters.UUIDFilter(method="filter_treatment")
    category = django_filters.UUIDFilter(method="filter_category")
    category_id = django_filters.UUIDFilter(method="filter_category")

    class Meta:
        model = Practitioner
        fields = ["clinic", "clinic_id", "type", "treatment", "treatment_id", "category", "category_id"]

    def filter_treatment(self, queryset, name, value):
        if value:
            return queryset.filter(
                treatments__id=value,
                treatments__is_active=True,
                treatments__deleted_at__isnull=True,
            ).distinct()
        return queryset

    def filter_category(self, queryset, name, value):
        if value:
            return queryset.filter(
                treatments__category_id=value,
                treatments__is_active=True,
                treatments__deleted_at__isnull=True,
            ).distinct()
        return queryset
