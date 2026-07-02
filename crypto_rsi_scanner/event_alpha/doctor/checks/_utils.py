"""Shared helpers for Event Alpha artifact-doctor check plugins."""

from __future__ import annotations

from collections.abc import Mapping, MutableSequence
from typing import Any


Messages = MutableSequence[str]


def ctx_value(ctx: object, name: str, default: Any = 0) -> Any:
    return getattr(ctx, name, default)


def ctx_mapping(ctx: object, name: str) -> Mapping[str, Any]:
    value = getattr(ctx, name, {})
    return value if isinstance(value, Mapping) else {}


def count(mapping: Mapping[str, Any], key: str) -> Any:
    return mapping.get(key, 0)


def emit(blockers: Messages, warnings: Messages, message: str, *, blocker: bool = False) -> None:
    (blockers if blocker else warnings).append(message)


def emit_count(
    blockers: Messages,
    warnings: Messages,
    mapping: Mapping[str, Any],
    key: str,
    *,
    blocker: bool = False,
    warning_only: bool = False,
) -> None:
    value = count(mapping, key)
    if not value:
        return
    emit(blockers, warnings, f"{key}={value}", blocker=blocker and not warning_only)
