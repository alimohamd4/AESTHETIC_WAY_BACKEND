import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.clinics.models import Clinic, ClinicStatus
from apps.media.models import MediaAsset
from apps.products.models import ContentStatus, Product


@pytest.mark.django_db
class TestProductAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.list_url = reverse("api_v1:products:product-list")

        self.clinic_active = Clinic.objects.create(
            name_en="Dermatology Clinic",
            status=ClinicStatus.ACTIVE,
            city="Dubai",
        )
        self.clinic_other = Clinic.objects.create(
            name_en="Beauty Center",
            status=ClinicStatus.ACTIVE,
            city="Abu Dhabi",
        )
        self.clinic_suspended = Clinic.objects.create(
            name_en="Suspended Clinic",
            status=ClinicStatus.SUSPENDED,
            city="Dubai",
        )

        # Active Product 1
        self.product_active = Product.objects.create(
            clinic=self.clinic_active,
            name_en="Hyaluronic Acid Serum",
            name_ar="سيروم حمض الهيالورونيك",
            description_en="Deep hydration serum for glowing skin",
            price=250.00,
            image="https://example.com/serum.jpg",
            is_active=True,
            status=ContentStatus.ACTIVE,
        )

        # Active Product 2 with media asset
        media = MediaAsset.objects.create(
            media_type="product_image",
            clinic=self.clinic_other,
            file="products/sunscreen.jpg",
            original_filename="sunscreen.jpg",
            file_size=2048,
            mime_type="image/jpeg",
        )
        self.product_other_clinic = Product.objects.create(
            clinic=self.clinic_other,
            name_en="SPF 50+ Sunscreen",
            price=180.00,
            media_asset=media,
            is_active=True,
            status=ContentStatus.ACTIVE,
        )

        # Inactive Product
        self.product_inactive = Product.objects.create(
            clinic=self.clinic_active,
            name_en="Out of Stock Cream",
            price=100.00,
            is_active=False,
            status=ContentStatus.ACTIVE,
        )

        # Soft-deleted Product
        self.product_deleted = Product.objects.create(
            clinic=self.clinic_active,
            name_en="Discontinued Toner",
            price=90.00,
            is_active=True,
            status=ContentStatus.ACTIVE,
            deleted_at=timezone.now(),
        )

        # Product from suspended clinic
        self.product_suspended_clinic = Product.objects.create(
            clinic=self.clinic_suspended,
            name_en="Suspended Clinic Product",
            price=150.00,
            is_active=True,
            status=ContentStatus.ACTIVE,
        )

    def test_public_product_list_active_and_non_deleted_only(self):
        response = self.client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        names = [p["name_en"] for p in response.json()["results"]]
        assert "Hyaluronic Acid Serum" in names
        assert "SPF 50+ Sunscreen" in names
        assert "Out of Stock Cream" not in names
        assert "Discontinued Toner" not in names
        assert "Suspended Clinic Product" not in names

    def test_clinic_filtering(self):
        response = self.client.get(self.list_url, {"clinic_id": str(self.clinic_active.id)})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "Hyaluronic Acid Serum"

    def test_search_products(self):
        response = self.client.get(self.list_url, {"search": "Sunscreen"})
        assert response.status_code == status.HTTP_200_OK
        results = response.json()["results"]
        assert len(results) == 1
        assert results[0]["name_en"] == "SPF 50+ Sunscreen"

    def test_product_detail(self):
        url = reverse("api_v1:products:product-detail", kwargs={"id": str(self.product_active.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name_en"] == "Hyaluronic Acid Serum"
        assert data["name_ar"] == "سيروم حمض الهيالورونيك"
        assert data["clinic"]["name_en"] == "Dermatology Clinic"
        assert float(data["price"]) == 250.00
        assert data["image_url"] == "https://example.com/serum.jpg"

    def test_image_url_fallback(self):
        url = reverse("api_v1:products:product-detail", kwargs={"id": str(self.product_other_clinic.id)})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "products/sunscreen.jpg" in data["image_url"]

    def test_inactive_or_deleted_product_detail_returns_404(self):
        url_inactive = reverse("api_v1:products:product-detail", kwargs={"id": str(self.product_inactive.id)})
        assert self.client.get(url_inactive).status_code == status.HTTP_404_NOT_FOUND

        url_deleted = reverse("api_v1:products:product-detail", kwargs={"id": str(self.product_deleted.id)})
        assert self.client.get(url_deleted).status_code == status.HTTP_404_NOT_FOUND

    def test_private_fields_not_exposed(self):
        response = self.client.get(self.list_url)
        item = response.json()["results"][0]
        assert "status" not in item
        assert "deleted_at" not in item
        assert "is_active" not in item
        assert "patient" not in item
