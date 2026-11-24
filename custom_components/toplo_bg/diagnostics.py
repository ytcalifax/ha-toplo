"""Safe diagnostics for Toplo.bg API and response failures."""

import json
import logging
import re
import traceback
from typing import Any

_LOGGER = logging.getLogger(__name__)
_DIAGNOSTIC_FIELDS = (
    "errorCode",
    "responseCode",
    "responseCodeDescription",
    "isSuccess",
    "isSuccessStatusCode",
    "errors",
    "error",
    "title",
    "detail",
    "message",
)
_SENSITIVE_KEY = re.compile(
    r"password|парола|token|secret|email|phone|address|owner|installation|"
    r"user.?id|client.?id|identification|bulstat|document|contract|number|name",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", re.IGNORECASE)
_LONG_NUMBER = re.compile(r"(?<!\d)\d{7,}(?!\d)")
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")
_SECRET_VALUE = re.compile(
    r"(?i)([\"']?(?:password|парола|token|refresh.?token|authorization|secret)"
    r"[\"']?\s*[:=]\s*[\"']?)[^\"'\s,;}]+"
)
_SAFE_CODE = re.compile(r"[A-Za-z0-9_.:-]{1,40}\Z")
_SENSITIVE_PARAM = re.compile(
    r"id|token|password|email|phone|address|owner|name|secret", re.IGNORECASE
)


def log_api_failure(
    *,
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
    status: int | None = None,
    content_type: str | None = None,
    response_bytes: int | None = None,
    diagnostics: dict[str, Any] | None = None,
    error: Exception | None = None,
) -> None:
    """Log request failure context without credentials or account data."""
    details: dict[str, Any] = {
        "method": method,
        "endpoint": endpoint,
        "query": _safe_params(params),
    }
    if status is not None:
        details["http_status"] = status
    if content_type is not None:
        details["content_type"] = content_type
    if response_bytes is not None:
        details["response_bytes"] = response_bytes
    if diagnostics:
        details["api_diagnostics"] = diagnostics
    if error is not None:
        details["exception_type"] = type(error).__name__
        if str(error):
            details["exception"] = redact_text(str(error))
        if error.__traceback__ is not None:
            details["traceback"] = traceback.format_tb(error.__traceback__)[-8:]
    _LOGGER.error("Toplo.bg API request failed: %s", json.dumps(details, ensure_ascii=False))


def log_login_rejected(payload: dict[str, Any]) -> None:
    """Log safe API status fields when Toplo.bg rejects login."""
    _LOGGER.error(
        "Toplo.bg login returned an unsuccessful result: %s",
        json.dumps(response_diagnostics(payload), ensure_ascii=False),
    )


def log_application_error(endpoint: str, payload: dict[str, Any]) -> None:
    """Log a successful HTTP response that reports an API-level failure."""
    _LOGGER.error(
        "Toplo.bg API reported failure: endpoint=%s diagnostics=%s",
        endpoint,
        json.dumps(response_diagnostics(payload), ensure_ascii=False),
    )


def log_invalid_shape(endpoint: str, expected: str, payload: Any) -> None:
    """Log response structure, never response values, when a schema is unexpected."""
    details: dict[str, Any] = {"actual_type": type(payload).__name__}
    if isinstance(payload, dict):
        details["keys"] = sorted(str(key) for key in payload)[:30]
        details["api_diagnostics"] = response_diagnostics(payload)
    elif isinstance(payload, list):
        details["item_count"] = len(payload)
        details["item_types"] = [type(item).__name__ for item in payload[:10]]
    _LOGGER.error(
        "Invalid Toplo.bg response shape: endpoint=%s expected=%s details=%s",
        endpoint,
        expected,
        json.dumps(details, ensure_ascii=False),
    )


def response_diagnostics(payload: Any) -> dict[str, Any]:
    """Extract status codes and structure from an API error payload."""
    if not isinstance(payload, dict):
        return {"response_type": type(payload).__name__}

    details: dict[str, Any] = {}
    for key in _DIAGNOSTIC_FIELDS:
        if key not in payload:
            continue
        value = payload[key]
        if key in ("errorCode", "responseCode", "isSuccess", "isSuccessStatusCode"):
            if isinstance(value, bool) or isinstance(value, int):
                details[key] = value
            elif isinstance(value, str) and _SAFE_CODE.fullmatch(value):
                details[key] = value
        else:
            details[key] = _safe_diagnostic_value(value, key)
    if "errors" in details:
        errors = payload["errors"]
        values = errors.get("$values") if isinstance(errors, dict) else errors
        details["errors_type"] = type(errors).__name__
        details["errors_count"] = len(values) if isinstance(values, list) else None
    if not details:
        details["response_keys"] = sorted(str(key) for key in payload)[:30]
    return details


def _safe_diagnostic_value(value: Any, key: str = "") -> Any:
    """Bound and redact structured API error details before they reach logs."""
    if key and _SENSITIVE_KEY.search(key):
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(child_key): _safe_diagnostic_value(child_value, str(child_key))
            for child_key, child_value in list(value.items())[:20]
        }
    if isinstance(value, list):
        return [_safe_diagnostic_value(item) for item in value[:10]]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return f"<{type(value).__name__}>"


def redact_text(value: str) -> str:
    """Redact common credentials and account identifiers from exception text."""
    value = _BEARER.sub("Bearer [redacted]", value)
    value = _SECRET_VALUE.sub(r"\1[redacted]", value)
    value = _EMAIL.sub("[email redacted]", value)
    value = _UUID.sub("[id redacted]", value)
    value = _LONG_NUMBER.sub("[number redacted]", value)
    return value[:500]


def _safe_params(params: dict[str, Any] | None) -> dict[str, Any]:
    """Redact identifiers while retaining date and filter values for diagnosis."""
    if not params:
        return {}
    return {
        key: "[redacted]" if _SENSITIVE_PARAM.search(key) else value
        for key, value in params.items()
    }
