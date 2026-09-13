import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.treatments.models import Category


@pytest.mark.django_db
class TestCategoryAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.url = reverse("api_v1:categories:category-list")
        self.cat1 = Category.objects.create(
            name_en="Face Treatments",
            name_ar="علاجات الوجه",
            slug="face-treatments",
            icon="https://example.com/face.png",
            display_order=10,
            is_active=True,
        )
        self.cat2 = Category.objects.create(
            name_en="Body Contouring",
            name_ar="نحت الجسم",
            slug="body-contouring",
            icon="https://example.com/body.png",
            display_order=5,
            is_active=True,
        )
        self.cat_inactive = Category.objects.create(
            name_en="Outdated Category",
            name_ar="فئة قديمة",
            slug="outdated-category",
            display_order=1,
            is_active=False,
        )

    def test_active_categories_returned_in_display_order(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        results = data["results"]
        assert len(results) == 2
        # Body (display_order 5) before Face (display_order 10)
        assert results[0]["id"] == str(self.cat2.id)
        assert results[0]["name_en"] == "Body Contouring"
        assert results[0]["name_ar"] == "نحت الجسم"
        assert results[0]["icon"] == "https://example.com/body.png"
        assert results[1]["id"] == str(self.cat1.id)

    def test_inactive_categories_excluded(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        ids = [item["id"] for item in response.json()["results"]]
        assert str(self.cat_inactive.id) not in ids

    def test_internal_fields_not_exposed(self):
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        item = response.json()["results"][0]
        assert "is_active" not in item
        assert "created_at" not in item
        assert "updated_at" not in item

    def test_pagination_envelope(self):
        response = self.client.get(self.url, {"per_page": 1})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "count" in data
        assert "next" in data
        assert "previous" in data
        assert "results" in data
        assert data["count"] == 2
        assert len(data["results"]) == 1
