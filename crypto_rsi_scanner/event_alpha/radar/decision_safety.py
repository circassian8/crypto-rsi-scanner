"""Pure fail-closed safety predicates for Crypto Radar Decision Model v2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math
from pathlib import Path
from typing import Any


SOURCE_SIDE_EFFECT_ATTESTATION = "decision_source_side_effect_safety_failed"
SOURCE_SECRET_ATTESTATION = "decision_source_secret_safety_failed"
SOURCE_PATH_ATTESTATION = "decision_source_path_safety_failed"
SOURCE_SAFETY_ATTESTATION_FIELDS = (
    SOURCE_SIDE_EFFECT_ATTESTATION,
    SOURCE_SECRET_ATTESTATION,
    SOURCE_PATH_ATTESTATION,
)


def source_safety_attestations(rows: Iterable[Mapping[str, Any]]) -> dict[str, bool]:
    """Reduce source-family safety failures to non-sensitive boolean facts."""

    materialized = tuple(row for row in rows if isinstance(row, Mapping))
    return {
        SOURCE_SIDE_EFFECT_ATTESTATION: any(has_unsafe_side_effect(row) for row in materialized),
        SOURCE_SECRET_ATTESTATION: any(has_unredacted_secret(row) for row in materialized),
        SOURCE_PATH_ATTESTATION: any(has_unsafe_operator_path(row) for row in materialized),
    }


def decision_safety_blockers(
    data: Mapping[str, Any],
    sources: Iterable[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Return fail-closed promotion blockers from root and source attestations."""

    rows = (data, *(row for row in sources if isinstance(row, Mapping)))
    blockers: list[str] = []
    if data.get("research_only") is not True:
        blockers.append("research_safety_invariant_failed")
    if any(
        has_unsafe_side_effect(row) or _attestation_failed(row, SOURCE_SIDE_EFFECT_ATTESTATION)
        for row in rows
    ):
        blockers.append("research_safety_invariant_failed")
    if any(
        has_unredacted_secret(row) or _attestation_failed(row, SOURCE_SECRET_ATTESTATION)
        for row in rows
    ):
        blockers.append("secret_safety_failed")
    if any(
        has_unsafe_operator_path(row) or _attestation_failed(row, SOURCE_PATH_ATTESTATION)
        for row in rows
    ):
        blockers.append("operator_path_safety_failed")
    return tuple(dict.fromkeys(blockers))


def has_unsafe_side_effect(data: Mapping[str, Any]) -> bool:
    return any(_mapping_has_unsafe_side_effect(row) for row in _mapping_tree(data))


def _mapping_has_unsafe_side_effect(data: Mapping[str, Any]) -> bool:
    if "research_only" in data and data.get("research_only") is not True:
        return True
    boolean_fields = (
        "normal_rsi_signal_written", "trade_created",
        "paper_trade_created", "created_alert",
        "notification_send_enabled", "execution_enabled", "paper_trading_enabled",
        "normal_rsi_routing_enabled", "sent",
    )
    if any(
        field in data and data.get(field) is not False
        for field in boolean_fields
    ):
        return True
    counter_fields = (
        "normal_rsi_signal_rows_written", "trades_created", "paper_trades_created",
        "triggered_fade_created", "telegram_sends", "strict_alerts_created",
    )
    return any(
        field in data and not _safe_zero_counter(data.get(field))
        for field in counter_fields
    )


def has_unredacted_secret(data: Mapping[str, Any]) -> bool:
    return any(_mapping_has_unredacted_secret(row) for row in _mapping_tree(data))


def _mapping_has_unredacted_secret(data: Mapping[str, Any]) -> bool:
    secret_names = {"api_key", "token", "secret", "password", "authorization"}
    safe_values = {"", "redacted", "<redacted>", "<hidden>", "<masked>", "***", "****"}
    for key, value in data.items():
        name = str(key).casefold()
        if name.endswith(("_redacted", "_env", "_env_var", "_required")):
            continue
        sensitive = name in secret_names or name.endswith(
            ("_api_key", "_token", "_secret", "_password", "_authorization")
        )
        if sensitive and str(value or "").strip().casefold() not in safe_values:
            return True
    return False


def has_unsafe_operator_path(data: Mapping[str, Any]) -> bool:
    return any(_mapping_has_unsafe_operator_path(row) for row in _mapping_tree(data))


def _mapping_has_unsafe_operator_path(data: Mapping[str, Any]) -> bool:
    for key, value in data.items():
        name = str(key).casefold()
        if name.endswith("_abs_debug") or not (
            name == "path" or name.endswith(("_path", "_paths"))
        ):
            continue
        if any(
            str(item or "") and Path(str(item)).expanduser().is_absolute()
            for item in _path_values(value)
        ):
            return True
    return False


def _path_values(value: object) -> Iterable[object]:
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _path_values(nested)
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for nested in value:
            yield from _path_values(nested)
    else:
        yield value


def _attestation_failed(row: Mapping[str, Any], field: str) -> bool:
    return field in row and row.get(field) is not False


def _mapping_tree(value: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _mapping_tree(child)
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _mapping_tree(child)


def _safe_zero_counter(value: object) -> bool:
    if value is False:
        return True
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value)) and float(value) == 0.0


__all__ = (
    "SOURCE_PATH_ATTESTATION",
    "SOURCE_SAFETY_ATTESTATION_FIELDS",
    "SOURCE_SECRET_ATTESTATION",
    "SOURCE_SIDE_EFFECT_ATTESTATION",
    "decision_safety_blockers",
    "has_unredacted_secret",
    "has_unsafe_operator_path",
    "has_unsafe_side_effect",
    "source_safety_attestations",
)
