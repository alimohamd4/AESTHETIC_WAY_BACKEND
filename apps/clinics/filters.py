import django_filters

from apps.clinics.models import Clinic


class ClinicFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(field_name="city", lookup_expr="iexact")
    emirate = django_filters.CharFilter(field_name="emirate", lookup_expr="iexact")
    category = django_filters.UUIDFilter(method="filter_category")
    category_id = django_filters.UUIDFilter(method="filter_category")

    class Meta:
        model = Clinic
        fields = ["city", "emirate", "category", "category_id"]

    def filter_category(self, queryset, name, value):
        if value:
            return queryset.filter(
                treatments__category_id=value,
                treatments__is_active=True,
                treatments__status="active",
                treatments__deleted_at__isnull=True,
            ).distinct()
        return queryset
