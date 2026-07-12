"""Pure fail-closed safety predicates for Crypto Radar Decision Model v2."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


def has_unsafe_side_effect(data: Mapping[str, Any]) -> bool:
    return any(_mapping_has_unsafe_side_effect(row) for row in _mapping_tree(data))


def _mapping_has_unsafe_side_effect(data: Mapping[str, Any]) -> bool:
    if data.get("research_only") is False:
        return True
    fields = (
        "normal_rsi_signal_written", "normal_rsi_signal_rows_written",
        "triggered_fade_created", "trade_created", "trades_created",
        "paper_trade_created", "paper_trades_created", "created_alert",
        "notification_send_enabled", "execution_enabled", "paper_trading_enabled",
        "normal_rsi_routing_enabled", "sent", "telegram_sends", "strict_alerts_created",
    )
    return any(_truthy(data.get(field)) for field in fields)


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
        if name.endswith("_abs_debug") or not name.endswith(("_path", "_paths")):
            continue
        values = value if isinstance(value, (list, tuple, set)) else (value,)
        if any(str(item or "") and Path(str(item)).is_absolute() for item in values):
            return True
    return False


def _mapping_tree(value: object) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _mapping_tree(child)
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _mapping_tree(child)


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


__all__ = ("has_unredacted_secret", "has_unsafe_operator_path", "has_unsafe_side_effect")
