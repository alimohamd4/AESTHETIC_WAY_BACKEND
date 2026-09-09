"""App configuration endpoints � stub for Phase 1."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema


@extend_schema(tags=["App Config"], summary="App configuration")
class AppConfigView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"app_name": "AESTHETIC WAY", "version_min": "1.0.0"})


@extend_schema(tags=["App Config"], summary="Support contact information")
class SupportInfoView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({
            "platform_name": "AESTHETIC WAY",
            "support_phone": "+971581989252",
            "support_whatsapp": "+971581989252",
        })
