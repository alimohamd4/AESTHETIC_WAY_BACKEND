"""App configuration endpoints."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PlatformSetting

DEFAULT_SUPPORT_PHONE = "+971581989252"
DEFAULT_SUPPORT_WHATSAPP = "+971581989252"
DEFAULT_SUPPORT_DISPLAY = "+971 58 198 9252"


def _format_phone_display(phone: str) -> str:
    cleaned = str(phone).strip()
    if cleaned.startswith("+971") and len(cleaned) == 13:
        return f"{cleaned[:4]} {cleaned[4:6]} {cleaned[6:9]} {cleaned[9:]}"
    return cleaned


@extend_schema(tags=["App Config"], summary="App configuration", responses={200: dict})
class AppConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"app_name": "AESTHETIC WAY", "version_min": "1.0.0"})


@extend_schema(tags=["App Config"], summary="Support contact information", responses={200: dict})
class SupportInfoView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        phone_setting = PlatformSetting.objects.filter(key="support_phone").first()
        whatsapp_setting = PlatformSetting.objects.filter(key="support_whatsapp").first()
        display_setting = PlatformSetting.objects.filter(key="support_phone_display").first()

        support_phone = DEFAULT_SUPPORT_PHONE
        if phone_setting and phone_setting.value is not None:
            val = phone_setting.value
            support_phone = str(val if not isinstance(val, dict) else val.get("value", DEFAULT_SUPPORT_PHONE)).strip()

        support_whatsapp = DEFAULT_SUPPORT_WHATSAPP
        if whatsapp_setting and whatsapp_setting.value is not None:
            val = whatsapp_setting.value
            support_whatsapp = str(val if not isinstance(val, dict) else val.get("value", DEFAULT_SUPPORT_WHATSAPP)).strip()

        if display_setting and display_setting.value is not None:
            val = display_setting.value
            support_phone_display = str(val if not isinstance(val, dict) else val.get("value", DEFAULT_SUPPORT_DISPLAY)).strip()
        else:
            support_phone_display = _format_phone_display(support_phone)

        return Response({
            "platform_name": "AESTHETIC WAY",
            "support_phone": support_phone,
            "support_whatsapp": support_whatsapp,
            "support_phone_display": support_phone_display,
        })
