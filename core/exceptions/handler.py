"""
Global exception handler for AESTHETIC WAY API.
Returns standardized error envelopes for all exceptions.

Standard error format:
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Human-readable message",
        "fields": {"field_name": ["error message"]}
    }
}
"""
import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied as DRFPermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

# Mapping from DRF exception class to our API error code
ERROR_CODE_MAP = {
    NotAuthenticated: "AUTHENTICATION_REQUIRED",
    AuthenticationFailed: "AUTHENTICATION_FAILED",
    DRFPermissionDenied: "PERMISSION_DENIED",
    NotFound: "NOT_FOUND",
    ValidationError: "VALIDATION_ERROR",
    Throttled: "RATE_LIMIT_EXCEEDED",
}


def custom_exception_handler(exc, context):
    """
    Custom exception handler that wraps all errors in a standardized envelope.
    Called for every unhandled exception in DRF views.
    """
    # Convert Django exceptions to DRF equivalents
    if isinstance(exc, Http404):
        exc = NotFound(detail=str(exc) or "The requested resource was not found.")
    elif isinstance(exc, PermissionDenied):
        exc = DRFPermissionDenied(detail=str(exc) or "You do not have permission to perform this action.")

    # Let DRF do its default handling first
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception � return 500
        logger.exception(
            "Unhandled exception in view %s",
            context.get("view", "unknown"),
            exc_info=exc,
        )
        return Response(
            {
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred. Please try again later.",
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # Determine error code
    error_code = ERROR_CODE_MAP.get(type(exc), "API_ERROR")

    # Build standardized error body
    error_body = {
        "code": error_code,
        "message": _get_message(exc),
    }

    # Add field-level errors for validation errors
    if isinstance(exc, ValidationError):
        fields = _normalize_validation_errors(exc.detail)
        if fields:
            error_body["fields"] = fields

    # Add retry info for throttling
    if isinstance(exc, Throttled):
        error_body["retry_after"] = exc.wait

    response.data = {"error": error_body}
    return response


def _get_message(exc: APIException) -> str:
    """Extract a single human-readable message from the exception."""
    if isinstance(exc, ValidationError):
        # For validation errors, return a generic message; fields are in "fields"
        return "One or more fields failed validation."
    if hasattr(exc, "detail"):
        detail = exc.detail
        if isinstance(detail, list) and len(detail) > 0:
            return str(detail[0])
        if isinstance(detail, str):
            return detail
        if hasattr(detail, "code"):
            return str(detail)
    return str(exc)


def _normalize_validation_errors(detail, prefix: str = "") -> dict:
    """
    Recursively flatten DRF validation error detail into a flat dict.
    Example: {"phone": ["This field is required."]}
    """
    result = {}
    if isinstance(detail, dict):
        for field, errors in detail.items():
            key = f"{prefix}.{field}" if prefix else field
            result.update(_normalize_validation_errors(errors, prefix=key))
    elif isinstance(detail, list):
        messages = []
        for item in detail:
            if isinstance(item, str):
                messages.append(item)
            elif hasattr(item, "detail"):
                messages.append(str(item))
            else:
                messages.append(str(item))
        if messages and prefix:
            result[prefix] = messages
    return result
