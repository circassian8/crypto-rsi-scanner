"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` (serialization)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status
from ....event_providers import cryptopanic as cryptopanic_provider
from ...artifacts import paths as event_artifact_paths
from ...providers import bybit_announcements_preflight as event_bybit_announcements_preflight
from ...providers import coinalyze_preflight as event_coinalyze_preflight
from ...providers import dex_onchain_readiness as event_dex_onchain_readiness
from ...providers import official_exchange_activation as event_official_exchange_activation
from ...providers import provider_health as event_provider_health
from ...providers import source_packs as event_source_packs
from ...providers import unlock_calendar_preflight as event_unlock_calendar_preflight
from .models import *  # noqa: F403

def _coinalyze_supported_metric_status(
    preflight_payload: Mapping[str, Any],
    rehearsal_payload: Mapping[str, Any],
) -> dict[str, str]:
    for payload in (rehearsal_payload, preflight_payload):
        status = payload.get("supported_metric_status")
        if isinstance(status, Mapping):
            return {str(key): str(value) for key, value in status.items() if str(key)}
    return {}
def _coinalyze_metric_status_line(status: Mapping[str, str] | None) -> str:
    if not status:
        return "none"
    metrics = (
        "open_interest",
        "funding_rate",
        "predicted_funding",
        "liquidations",
        "long_short_ratio",
        "basis",
        "perp_volume",
    )
    parts = [f"{metric}={status.get(metric)}" for metric in metrics if status.get(metric)]
    return ", ".join(parts) if parts else "none"
def _count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0
def _read_json(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, Mapping) else {}
def _status(row: Mapping[str, Any]) -> str:
    return str(row.get("status") or row.get("evidence_acquisition_status") or "").strip()
def _evidence_absence_meaningful(
    pack_name: str,
    healthy: Iterable[str],
    degraded: Iterable[str],
) -> bool:
    healthy_set = set(healthy)
    degraded_set = set(degraded)
    if not healthy_set:
        return False
    if healthy_set <= _BROAD_CONTEXT_PROVIDERS and degraded_set:
        return False
    pack = event_source_packs.get_source_pack(pack_name)
    preferred = set(pack.preferred_providers)
    return bool((healthy_set & preferred) & _HIGH_SPECIFICITY_PROVIDERS)
def _sorted_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(dict.fromkeys(str(value) for value in values if str(value))))
def _join(values: Iterable[str]) -> str:
    items = _sorted_tuple(values)
    return ", ".join(items) if items else "none"
