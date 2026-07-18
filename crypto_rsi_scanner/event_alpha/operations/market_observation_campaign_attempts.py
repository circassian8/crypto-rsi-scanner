"""Canonical reconciliation for campaign-attempt audit representations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .market_no_send_attempt import ATTEMPT_LEDGER_FILENAME, LATEST_ATTEMPT_FILENAME
from .market_no_send_io import read_json_object, read_jsonl
from .market_no_send_models import MarketNoSendError


PILOT_AUDIT_FILENAME = "event_market_no_send_pilot_audit.json"
_ATTEMPT_FIELDS = (
    "attempt_id",
    "artifact_namespace",
    "run_id",
    "observed_at",
    "attempt_status",
    "provider",
    "provider_call_attempted",
    "provider_request_succeeded",
    "failure_class",
    "candidate_source_mode",
    "no_send",
    "research_only",
)
def load_root_attempts(base: Path) -> list[dict[str, Any]]:
    """Load bounded root receipts without treating duplicate views as attempts."""

    raw: list[Mapping[str, Any]] = []
    audit = _read_json(base / PILOT_AUDIT_FILENAME)
    if audit:
        raw.append(audit)
    receipt = _read_json(base / LATEST_ATTEMPT_FILENAME)
    if receipt:
        raw.append(receipt)
    raw.extend(read_jsonl(base / ATTEMPT_LEDGER_FILENAME))
    return [
        attempt_row({}, row, namespace=_text(row.get("artifact_namespace")) or "unknown")
        for row in raw
        if is_live_market_attempt({}, row)
    ]


def attempt_row(
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    namespace: str,
) -> dict[str, Any]:
    """Project one manifest/audit pair into the closed campaign attempt shape."""

    status = _text(
        manifest.get("status")
        or audit.get("attempt_status")
        or audit.get("status")
        or "unknown"
    )
    return {
        "attempt_id": _text(audit.get("attempt_id")) or None,
        "artifact_namespace": namespace,
        "run_id": _text(
            manifest.get("run_id") or audit.get("exact_run_id") or audit.get("run_id")
        ) or None,
        "observed_at": _safe_timestamp(
            manifest.get("observed_at")
            or audit.get("observed_at")
            or audit.get("generated_at")
        ),
        "attempt_status": status,
        "provider": _text(
            manifest.get("provider") or audit.get("provider") or "coingecko"
        ),
        "provider_call_attempted": _strict_true(
            manifest, audit, "provider_call_attempted"
        ),
        "provider_request_succeeded": _strict_true(
            manifest, audit, "provider_request_succeeded"
        ),
        "failure_class": _safe_error_class(
            manifest.get("failure_class")
            or audit.get("failure_class")
            or audit.get("error_class")
        ),
        "candidate_source_mode": _text(
            manifest.get("candidate_source_mode")
            or audit.get("candidate_source_mode")
            or "preflight_only"
        ),
        "no_send": (
            manifest.get("no_send") is True
            or audit.get("no_send") is True
            or _mapping(audit.get("safety")).get("no_send") is True
        ),
        "research_only": (
            manifest.get("research_only") is True
            or audit.get("research_only") is True
            or _mapping(audit.get("safety")).get("research_only") is True
        ),
    }


def deduplicate_attempts(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Reconcile root receipts and namespace projections into terminal attempts.

    ``attempt_id`` remains the identity of individually recorded root attempts.
    A namespace projection has no attempt ID, so it may enrich a root receipt
    only when namespace and observation time identify exactly one receipt and
    all terminal fields agree. Ambiguous or contradictory evidence fails closed
    instead of changing attempt counts.
    """

    identified: dict[tuple[Any, ...], dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for source in rows:
        row = _closed_attempt(source)
        attempt_id = _text(row.get("attempt_id"))
        if not attempt_id:
            anonymous.append(row)
            continue
        key = ("attempt_id", attempt_id)
        current = identified.get(key)
        identified[key] = (
            row if current is None else _merge_attempt_rows(current, row)
        )

    for row in sorted(anonymous, key=attempt_sort_key):
        matches = [
            key
            for key, identified_row in identified.items()
            if key[0] == "attempt_id"
            if _same_namespace_cycle(identified_row, row)
        ]
        if len(matches) > 1:
            raise MarketNoSendError(
                "campaign attempt namespace projection is ambiguous"
            )
        if matches:
            key = matches[0]
            identified[key] = _merge_attempt_rows(identified[key], row)
            continue
        key = _legacy_attempt_key(row)
        current = identified.get(key)
        identified[key] = row if current is None else _merge_attempt_rows(current, row)
    return sorted(identified.values(), key=attempt_sort_key)


def is_live_market_attempt(
    manifest: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> bool:
    mode = _text(manifest.get("data_mode") or audit.get("data_mode")).casefold()
    acquisition = _text(
        manifest.get("data_acquisition_mode") or audit.get("data_acquisition_mode")
    ).casefold()
    candidate_mode = _text(
        manifest.get("candidate_source_mode") or audit.get("candidate_source_mode")
    ).casefold()
    provider = _text(manifest.get("provider") or audit.get("provider")).casefold()
    return bool(
        mode == "live"
        or acquisition in {"live_provider", "preflight_only"}
        or candidate_mode in {"live_no_send", "preflight_only"}
        or (
            provider == "coingecko"
            and audit.get("row_type")
            in {
                "event_market_no_send_pilot_audit",
                "event_market_no_send_latest_attempt",
            }
        )
    ) and candidate_mode != "mocked_fixture" and mode != "mock"


def attempt_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _text(row.get("observed_at")),
        _text(row.get("artifact_namespace")),
        _text(row.get("run_id")),
        _text(row.get("attempt_id")),
    )


def _closed_attempt(row: Mapping[str, Any]) -> dict[str, Any]:
    return {field: row.get(field) for field in _ATTEMPT_FIELDS}


def _merge_attempt_rows(
    first: Mapping[str, Any],
    second: Mapping[str, Any],
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for field in _ATTEMPT_FIELDS:
        left = first.get(field)
        right = second.get(field)
        if left in (None, ""):
            merged[field] = right
        elif right in (None, ""):
            merged[field] = left
        elif left == right:
            merged[field] = left
        else:
            raise MarketNoSendError(
                f"campaign attempt representations conflict: {field}"
            )
    return merged


def _same_namespace_cycle(
    identified: Mapping[str, Any],
    anonymous: Mapping[str, Any],
) -> bool:
    namespace = _text(anonymous.get("artifact_namespace"))
    observed_at = _text(anonymous.get("observed_at"))
    return bool(
        namespace
        and namespace != "unknown"
        and observed_at
        and _text(identified.get("artifact_namespace")) == namespace
        and _text(identified.get("observed_at")) == observed_at
    )


def _legacy_attempt_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    values = tuple(row.get(field) for field in _ATTEMPT_FIELDS if field != "attempt_id")
    return ("legacy_attempt", *values)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return read_json_object(path)
    except (MarketNoSendError, OSError):
        return {}


def _strict_true(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
    field: str,
) -> bool:
    if field in primary:
        return primary.get(field) is True
    return secondary.get(field) is True


def _safe_error_class(value: Any) -> str | None:
    text = _text(value)
    if not text or len(text) > 80:
        return None
    return text if all(char.isalnum() or char in "_-." for char in text) else None


def _safe_timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else None


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return str(value).strip() if value not in (None, "") else ""


__all__ = (
    "attempt_row",
    "attempt_sort_key",
    "deduplicate_attempts",
    "is_live_market_attempt",
    "load_root_attempts",
)
