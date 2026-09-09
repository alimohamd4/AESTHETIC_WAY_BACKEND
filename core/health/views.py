"""
Health check endpoint for AESTHETIC WAY API.
Returns 200 with system status.
"""
from django.db import connection, OperationalError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(
    tags=["Health"],
    summary="System health check",
    description="Returns 200 if the service is healthy. Checks DB connectivity.",
    responses={200: OpenApiResponse(description="Service healthy"), 503: OpenApiResponse(description="Service degraded")},
)
class HealthCheckView(APIView):
    """GET /api/v1/health/ � Returns service health status."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        health = {"status": "healthy", "checks": {}}

        # Database check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health["checks"]["database"] = "ok"
        except OperationalError:
            health["checks"]["database"] = "error"
            health["status"] = "degraded"

        http_status = (
            status.HTTP_200_OK if health["status"] == "healthy"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return Response(health, status=http_status)
