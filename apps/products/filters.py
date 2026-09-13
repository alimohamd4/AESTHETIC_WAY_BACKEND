import django_filters

from apps.products.models import Product


class ProductFilter(django_filters.FilterSet):
    clinic = django_filters.UUIDFilter(field_name="clinic_id")
    clinic_id = django_filters.UUIDFilter(field_name="clinic_id")

    class Meta:
        model = Product
        fields = ["clinic", "clinic_id"]
