"""Closed non-secret status values for secret-like artifact field names."""

from __future__ import annotations

from typing import Any


SECRET_METADATA_STATUS_VALUES = {
    "live_authorization_status": frozenset(
        {
            "absent",
            "missing_configuration",
            "not_defined",
            "not_required",
            "present",
        }
    ),
}


def is_safe_secret_metadata_status(field_name: str, value: Any) -> bool:
    """Accept only exact typed status words, never arbitrary secret material."""

    allowed = SECRET_METADATA_STATUS_VALUES.get(field_name)
    return bool(
        allowed is not None
        and isinstance(value, str)
        and value in allowed
    )


__all__ = ("SECRET_METADATA_STATUS_VALUES", "is_safe_secret_metadata_status")
