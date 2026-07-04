"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` (recommendations)."""

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

def _recommendation_lines(report: EventAlphaSourceCoverageReport) -> list[str]:
    provider_missing_counts: dict[str, int] = {}
    provider_gap_counts: dict[str, int] = {}
    for pack in report.packs:
        gap_weight = max(1, pack.candidates_blocked_by_coverage_gap)
        for provider in pack.missing_providers:
            provider_missing_counts[provider] = provider_missing_counts.get(provider, 0) + gap_weight
        for provider in pack.degraded_or_backoff_providers:
            provider_gap_counts[provider] = provider_gap_counts.get(provider, 0) + gap_weight
    if not provider_missing_counts and not provider_gap_counts:
        return ["- coverage is currently sufficient for the tracked source packs"]
    combined = {
        provider: provider_missing_counts.get(provider, 0) + provider_gap_counts.get(provider, 0)
        for provider in set(provider_missing_counts) | set(provider_gap_counts)
    }
    top = sorted(
        combined,
        key=lambda item: (
            -_provider_lane_priority(item),
            -combined[item],
            item,
        ),
    )[:5]
    lines: list[str] = []
    for provider in top:
        reason = []
        if provider_missing_counts.get(provider):
            reason.append(f"missing_in_packs={provider_missing_counts[provider]}")
        if provider_gap_counts.get(provider):
            reason.append(f"degraded_or_backoff_in_packs={provider_gap_counts[provider]}")
        lines.append(f"- {provider}: " + ", ".join(reason))
    return lines
def _pack_recommended_actions(
    pack_name: str,
    *,
    missing: Iterable[str],
    degraded: Iterable[str],
    blocked: int,
    skipped_budget: int,
    rejected_only: int,
    provider_unavailable: int,
    satisfied_providers: Iterable[str] = (),
) -> tuple[str, ...]:
    actions: list[str] = []
    missing_set = set(missing)
    degraded_set = set(degraded)
    satisfied = set(satisfied_providers)
    if blocked or missing_set or degraded_set:
        for provider in sorted(missing_set):
            if provider in satisfied:
                continue
            actions.append(_provider_setup_action(provider, status="missing"))
        for provider in sorted(degraded_set):
            if provider in satisfied:
                continue
            actions.append(_provider_setup_action(provider, status="degraded"))
    if skipped_budget:
        actions.append("raise evidence-acquisition query/candidate budget for this source pack")
    if rejected_only:
        actions.append("inspect rejected evidence samples and add stricter query terms before trusting absence")
    if provider_unavailable:
        actions.append("run provider health report/reset before treating missing evidence as meaningful")
    if pack_name == "market_anomaly_pack" and "defillama" in missing_set:
        actions.append("add or enable DefiLlama-style protocol metrics before relying on market-anomaly confirmation")
    return tuple(dict.fromkeys(action for action in actions if action))
