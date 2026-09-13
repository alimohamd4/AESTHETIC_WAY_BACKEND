import django_filters

from apps.offers.models import Offer


class OfferFilter(django_filters.FilterSet):
    clinic = django_filters.UUIDFilter(field_name="clinic_id")
    clinic_id = django_filters.UUIDFilter(field_name="clinic_id")

    class Meta:
        model = Offer
        fields = ["clinic", "clinic_id"]
