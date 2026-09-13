import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.app_config.models import PlatformSetting


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestAppConfig:
    def test_app_config_endpoint(self, api_client):
        url = reverse("api_v1:app_config:app-config")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["app_name"] == "AESTHETIC WAY"
        assert "version_min" in data

    def test_default_support_info(self, api_client):
        url = reverse("api_v1:app_config:support-info")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["platform_name"] == "AESTHETIC WAY"
        assert data["support_phone"] == "+971581989252"
        assert data["support_whatsapp"] == "+971581989252"
        assert data["support_phone_display"] == "+971 58 198 9252"

    def test_dynamic_support_info_override(self, api_client):
        # Configure custom settings via PlatformSetting
        PlatformSetting.objects.create(
            key="support_phone",
            value="+971509876543"
        )
        PlatformSetting.objects.create(
            key="support_whatsapp",
            value="+971509876543"
        )

        url = reverse("api_v1:app_config:support-info")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["support_phone"] == "+971509876543"
        assert data["support_whatsapp"] == "+971509876543"
        assert data["support_phone_display"] == "+971 50 987 6543"

    def test_dynamic_support_info_dict_override(self, api_client):
        # Configure json dict values
        PlatformSetting.objects.create(
            key="support_phone",
            value={"value": "+971521112233"}
        )
        PlatformSetting.objects.create(
            key="support_phone_display",
            value={"value": "+971 (52) 111-2233"}
        )

        url = reverse("api_v1:app_config:support-info")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["support_phone"] == "+971521112233"
        assert data["support_phone_display"] == "+971 (52) 111-2233"

    def test_accept_language_header_handling(self, api_client):
        url = reverse("api_v1:app_config:app-config")

        # Test Arabic
        res_ar = api_client.get(url, HTTP_ACCEPT_LANGUAGE="ar")
        assert res_ar.status_code == status.HTTP_200_OK

        # Test English
        res_en = api_client.get(url, HTTP_ACCEPT_LANGUAGE="en")
        assert res_en.status_code == status.HTTP_200_OK

        # Test Unsupported / Fallback
        res_fallback = api_client.get(url, HTTP_ACCEPT_LANGUAGE="fr-FR,fr;q=0.9,en;q=0.8")
        assert res_fallback.status_code == status.HTTP_200_OK
