"""Standardized error responses and exception handling per Section 5.10."""

from typing import Any

from rest_framework import status
from rest_framework.response import Response


def error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> Response:
    """Format standard API error envelope.

    {"error": {"code": "...", "message": "...", "details": {...}}}
    """
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    return Response(payload, status=status_code)
