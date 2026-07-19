"""Scheduled catalyst and unlock artifacts for Event Alpha research.

This module normalizes fixture or explicitly configured calendar/unlock payloads
into local research artifacts. It is intentionally artifact-only: it does not
send notifications, open paper trades, write normal RSI rows, execute orders, or
create ``TRIGGERED_FADE``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.radar.market_reaction as event_market_reaction
from ..artifacts import schema_v1
from ...event_providers.manual_json import parse_datetime
from ...event_providers import tokenomist_v5
from . import market_anomaly_receipt


SCHEDULED_CATALYSTS_FILENAME = "event_scheduled_catalysts.jsonl"
UNLOCK_CANDIDATES_FILENAME = "event_unlock_candidates.jsonl"
SCHEDULED_CATALYST_REPORT_FILENAME = "event_scheduled_catalyst_report.md"
UNLOCK_RISK_REPORT_FILENAME = "event_unlock_risk_report.md"

STRUCTURED_UNLOCK_CLASSES = {
    "structured_unlock",
    "official_project",
    "official_exchange",
    "supply_data",
}
TRUSTED_CALENDAR_UNLOCK_CLASS = "structured_calendar"
STRUCTURED_CALENDAR_CLASSES = {
    "structured_calendar",
    "official_project",
    "official_exchange",
}

POSITIVE_EVENT_TYPES = {
    "governance_vote",
    "protocol_upgrade",
    "mainnet",
    "testnet",
    "airdrop",
    "staking_reward",
    "other",
}


@dataclass(frozen=True)
class ScheduledCatalystScanResult:
    namespace_dir: Path
    scheduled_path: Path
    unlock_path: Path
    scheduled_report_path: Path
    unlock_report_path: Path
    scheduled_count: int
    unlock_count: int
    scheduled_events: tuple[dict[str, Any], ...]
    unlock_candidates: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...] = ()


def run_scheduled_catalyst_scan(
    *,
    namespace_dir: str | Path,
    provider_paths: Mapping[str, str | Path | None],
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    observed_at: datetime | str | None = None,
    calendar_provider_name: str = "coinmarketcal",
    calendar_rows: Iterable[Mapping[str, Any]] | None = None,
    include_empty_unlock_artifacts: bool = True,
) -> ScheduledCatalystScanResult:
    """Normalize configured scheduled catalyst fixtures and write artifacts."""
    if not isinstance(include_empty_unlock_artifacts, bool):
        raise ValueError("include_empty_unlock_artifacts must be a boolean")
    directory = Path(namespace_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    warnings: list[str] = []
    scheduled_rows: list[dict[str, Any]] = []
    unlock_rows: list[dict[str, Any]] = []

    tokenomist_path = provider_paths.get("tokenomist")
    if tokenomist_path is None:
        warnings.append("tokenomist:not_configured")
    else:
        unlock_items = _load_tokenomist_items(tokenomist_path)
        if not unlock_items:
            warnings.append("tokenomist:no_fixture_rows")
        for item in unlock_items:
            event = normalize_scheduled_catalyst_event(
                item,
                provider="tokenomist",
                observed_at=observed,
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode=run_mode,
                run_id=run_id,
                forced_event_type=_unlock_event_type(item),
                forced_source_class=str(item.get("source_class") or "structured_unlock"),
            )
            scheduled_rows.append(event)
            unlock_rows.append(_unlock_candidate_for_event(event, item))

    messari_path = provider_paths.get("messari_unlocks")
    if messari_path is None:
        warnings.append("messari_unlocks:not_configured")
    else:
        unlock_items = tuple(_normalize_messari_unlock_item(item) for item in _load_messari_unlock_items(messari_path))
        if not unlock_items:
            warnings.append("messari_unlocks:no_fixture_rows")
        for item in unlock_items:
            event = normalize_scheduled_catalyst_event(
                item,
                provider="messari_unlocks",
                observed_at=observed,
                profile=profile,
                artifact_namespace=artifact_namespace,
                run_mode=run_mode,
                run_id=run_id,
                forced_event_type=_unlock_event_type(item),
                forced_source_class=str(item.get("source_class") or "structured_unlock"),
            )
            scheduled_rows.append(event)
            unlock_rows.append(_unlock_candidate_for_event(event, item))

    calendar_provider = _provider_name(calendar_provider_name)
    calendar_path = provider_paths.get("coinmarketcal")
    if calendar_rows is not None:
        calendar_items = tuple(
            dict(item) for item in calendar_rows if isinstance(item, Mapping)
        )
    elif calendar_path is None:
        calendar_items = None
        warnings.append(f"{calendar_provider}:not_configured")
    else:
        calendar_items = _load_calendar_items(calendar_path)
    if calendar_items is not None:
        if not calendar_items:
            warnings.append(f"{calendar_provider}:no_rows")
        calendar_scheduled, calendar_unlocks = normalize_calendar_catalyst_rows(
            calendar_items,
            provider=calendar_provider,
            observed_at=observed,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
        )
        scheduled_rows.extend(calendar_scheduled)
        unlock_rows.extend(calendar_unlocks)

    scheduled_path = directory / SCHEDULED_CATALYSTS_FILENAME
    unlock_path = directory / UNLOCK_CANDIDATES_FILENAME
    scheduled_report_path = directory / SCHEDULED_CATALYST_REPORT_FILENAME
    unlock_report_path = directory / UNLOCK_RISK_REPORT_FILENAME
    include_unlock_artifacts = bool(unlock_rows) or include_empty_unlock_artifacts
    artifact_payloads = {
        SCHEDULED_CATALYSTS_FILENAME: _jsonl_bytes(
            scheduled_path,
            scheduled_rows,
        ),
    }
    if include_unlock_artifacts:
        artifact_payloads[UNLOCK_CANDIDATES_FILENAME] = _jsonl_bytes(
            unlock_path,
            unlock_rows,
        )
    artifact_payloads[SCHEDULED_CATALYST_REPORT_FILENAME] = (
        format_scheduled_catalyst_report(
            scheduled_rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            warnings=warnings,
        ).encode("utf-8")
    )
    if include_unlock_artifacts:
        artifact_payloads[UNLOCK_RISK_REPORT_FILENAME] = format_unlock_risk_report(
            unlock_rows,
            profile=profile,
            artifact_namespace=artifact_namespace,
            warnings=warnings,
        ).encode("utf-8")
    market_anomaly_receipt.write_artifacts_atomic(
        directory,
        payloads=artifact_payloads,
        expected_names=tuple(artifact_payloads),
    )
    return ScheduledCatalystScanResult(
        namespace_dir=directory,
        scheduled_path=scheduled_path,
        unlock_path=unlock_path,
        scheduled_report_path=scheduled_report_path,
        unlock_report_path=unlock_report_path,
        scheduled_count=len(scheduled_rows),
        unlock_count=len(unlock_rows),
        scheduled_events=tuple(scheduled_rows),
        unlock_candidates=tuple(unlock_rows),
        warnings=tuple(warnings),
    )


def normalize_calendar_catalyst_rows(
    calendar_rows: Iterable[Mapping[str, Any]],
    *,
    provider: str,
    observed_at: datetime | str | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Purely derive scheduled and unlock rows from one calendar row stream."""

    provider_name = _provider_name(provider)
    scheduled_rows: list[dict[str, Any]] = []
    unlock_rows: list[dict[str, Any]] = []
    for raw_item in calendar_rows:
        if not isinstance(raw_item, Mapping):
            continue
        item = dict(raw_item)
        event_type = _calendar_event_type(item)
        event = normalize_scheduled_catalyst_event(
            item,
            provider=provider_name,
            observed_at=observed_at,
            profile=profile,
            artifact_namespace=artifact_namespace,
            run_mode=run_mode,
            run_id=run_id,
            forced_event_type=event_type,
            forced_source_class=str(
                item.get("source_class") or "structured_calendar"
            ),
        )
        scheduled_rows.append(event)
        if event_type == "token_unlock":
            unlock_rows.append(_unlock_candidate_for_event(event, item))
    return tuple(scheduled_rows), tuple(unlock_rows)


def _provider_name(value: object) -> str:
    text = str(value or "").strip().casefold().replace("-", "_")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]{0,63}", text):
        raise ValueError("calendar provider name is invalid")
    return text


def normalize_scheduled_catalyst_event(
    item: Mapping[str, Any],
    *,
    provider: str,
    observed_at: str | datetime | None = None,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    run_mode: str | None = None,
    run_id: str | None = None,
    forced_event_type: str | None = None,
    forced_source_class: str | None = None,
) -> dict[str, Any]:
    """Return one normalized scheduled catalyst row."""
    observed = _as_utc(_parse_time(observed_at) or datetime.now(timezone.utc))
    title = _title(item)
    description = _description(item)
    event_type = forced_event_type or _calendar_event_type(item)
    source_class = (forced_source_class or item.get("source_class") or _source_class_for_provider(provider)).strip()
    event_start = _event_time(item, "event_start_time", "event_time", "unlock_time", "unlock_date", "date_event", "start_time", "startDate")
    event_end = _event_time(item, "event_end_time", "end_time", "endDate")
    published_at = _event_time(item, "published_at", "created_at", "updated_at", "fetched_at")
    status = _event_status(item)
    symbols, coin_ids = _asset_identity(item)
    source_url = str(item.get("source_url") or item.get("url") or item.get("link") or "").strip() or None
    reason_codes = _scheduled_reason_codes(
        event_type=event_type,
        source_class=source_class,
        event_start=event_start,
        source_url=source_url,
        symbols=symbols,
        coin_ids=coin_ids,
        item=item,
    )
    confidence = _confidence(item, source_class=source_class, status=status, event_start=event_start, symbols=symbols)
    row = {
        "schema_version": 1,
        "row_type": "scheduled_catalyst_event",
        "profile": profile,
        "artifact_namespace": artifact_namespace,
        "run_mode": run_mode,
        "run_id": run_id,
        "provider": provider,
        "source_class": source_class,
        "event_id": str(item.get("event_id") or item.get("id") or f"{provider}:{_digest(title + '|' + str(event_start))}"),
        "scheduled_catalyst_id": f"sch:{provider}:{_digest(str(item.get('id') or title) + '|' + str(event_start))}",
        "title": title,
        "event_name": title,
        "description_summary": description,
        "url": source_url,
        "source_url": source_url,
        "published_at": published_at,
        "event_start_time": event_start,
        "event_end_time": event_end,
        "event_status": status,
        "symbols": symbols,
        "coin_ids": coin_ids,
        "symbol": symbols[0] if symbols else None,
        "coin_id": coin_ids[0] if coin_ids else None,
        "validated_symbol": symbols[0] if symbols else None,
        "validated_coin_id": coin_ids[0] if coin_ids else None,
        "event_type": event_type,
        "source_strength": _source_strength(source_class, status),
        "confidence": confidence,
        "reason_codes": reason_codes,
        "raw_payload_redacted": _redacted_payload(item),
        "source_pack": _source_pack_for_event_type(event_type),
        "impact_path_type": _impact_path_for_event_type(event_type),
        "structured_unlock_evidence": source_class in STRUCTURED_UNLOCK_CLASSES
        or (
            source_class == TRUSTED_CALENDAR_UNLOCK_CLASS
            and event_type in {"token_unlock", "vesting_cliff", "linear_emission"}
            and event_start
            and source_url
            and _optional_float(_first(item, "unlock_pct_circulating_supply", "unlock_pct_circulating", "percent_of_circulating_supply", "unlock_amount", "tokens_unlocked")) is not None
        ),
        "unlock_time": event_start if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "unlock_type": _unlock_type(item) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "cliff_or_linear": _cliff_or_linear(item) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "vesting_category": _vesting_category(item) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "event_timestamp_confidence": _event_timestamp_confidence(item, event_start=event_start, source_class=source_class),
        "tokens_unlocked": _optional_float(_first(item, "tokens_unlocked", "unlock_amount", "amount")) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "unlock_usd": _optional_float(_first(item, "unlock_usd", "unlock_value_usd", "value_usd")) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "unlock_value_to_market_cap_pct": (
            _optional_float(item.get("unlock_value_to_market_cap_pct"))
            if event_type in {"token_unlock", "vesting_cliff", "linear_emission"}
            else None
        ),
        "unlock_value_to_market_cap_unit": str(item.get("unlock_value_to_market_cap_unit") or "").strip() or None,
        "unlock_pct_circulating_supply": _optional_float(_first(item, "unlock_pct_circulating_supply", "unlock_pct_circulating", "percent_of_circulating_supply")) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "unlock_pct_circulating": _optional_float(_first(item, "unlock_pct_circulating_supply", "unlock_pct_circulating", "percent_of_circulating_supply")) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "unlock_pct_total_supply": _optional_float(_first(item, "unlock_pct_total_supply", "percent_of_total_supply")) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "unlock_vs_30d_adv": _optional_float(_first(item, "unlock_vs_30d_adv", "unlock_to_adv", "unlock_vs_adv")) if event_type in {"token_unlock", "vesting_cliff", "linear_emission"} else None,
        "observed_at": observed.isoformat(),
        "event_age_hours": _event_age_hours(event_start, observed),
        "market_snapshot": _market_snapshot(item),
        "derivatives_snapshot": _derivatives_snapshot(item),
        "supply_snapshot": _supply_snapshot(item),
        **_scheduled_provider_context(item),
        "research_only": True,
        "created_alert": False,
        "notification_send_enabled": False,
    }
    reaction = event_market_reaction.evaluate_market_reaction({
        **row,
        "evidence_quality_score": 92.0 if row["source_strength"] == "official_structured" else 55.0,
        "accepted_evidence_count": 1 if _structured_calendar_or_official(row) else 0,
        "accepted_evidence_reason_codes": reason_codes,
        "catalyst_fresh": _catalyst_fresh(row),
        "negative_catalyst": event_type == "token_unlock",
    })
    lane = reaction.opportunity_type
    why_not = list(reaction.why_not_alertable)
    if status == "canceled":
        lane = event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
        why_not.append("scheduled_event_canceled")
    elif status == "rumored":
        lane = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
        why_not.append("rumored_calendar_event")
    elif _stale_completed(row):
        lane = event_market_reaction.EventOpportunityType.DIAGNOSTIC.value
        why_not.append("stale_completed_catalyst")
    if not source_url:
        why_not.append("source_url_missing")
        if lane in {"EARLY_LONG_RESEARCH", "CONFIRMED_LONG_RESEARCH"}:
            lane = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    row.update({
        "market_state_snapshot": reaction.market_state_snapshot.to_dict(),
        "market_state": reaction.market_state,
        "opportunity_type": lane,
        "source_requirements_met": reaction.source_requirements_met,
        "market_requirements_met": reaction.market_requirements_met,
        "fade_requirements_met": reaction.fade_requirements_met,
        "why_now": reaction.why_now,
        "what_confirms": reaction.what_confirms,
        "what_invalidates": reaction.what_invalidates,
        "why_not_alertable": tuple(dict.fromkeys(why_not)),
    })
    return row


def _scheduled_provider_context(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider_api_version": item.get("provider_api_version"),
        "provider_query_at": item.get("provider_query_at"),
        "acquired_at": item.get("acquired_at"),
        "provider_page": item.get("provider_page"),
        "provider_page_size": item.get("provider_page_size"),
        "provider_total_pages": item.get("provider_total_pages"),
        "provider_total_rows": item.get("provider_total_rows"),
        "provider_snapshot_status": item.get("provider_snapshot_status"),
        "source_coverage_complete": item.get("source_coverage_complete"),
        "capture_mode": item.get("capture_mode"),
        "fixture_provenance": item.get("fixture_provenance"),
        "provider_call_performed": item.get("provider_call_performed"),
        "provider_authorization_created": item.get("provider_authorization_created"),
        "authority_eligible": item.get("authority_eligible"),
        "protocol_v2_evidence_eligible": item.get("protocol_v2_evidence_eligible"),
        "first_public_at": item.get("first_public_at"),
        "first_public_at_status": item.get("first_public_at_status"),
        "query_date_is_publication_time": item.get("query_date_is_publication_time"),
        "field_units": dict(item.get("field_units") or {})
        if isinstance(item.get("field_units"), Mapping)
        else {},
    }


def load_scheduled_catalysts(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    return tuple(_load_rows(path, SCHEDULED_CATALYSTS_FILENAME, "scheduled_catalyst_event"))


def load_unlock_candidates(path: str | Path | None) -> tuple[dict[str, Any], ...]:
    return tuple(_load_rows(path, UNLOCK_CANDIDATES_FILENAME, "unlock_event"))


def format_scheduled_catalyst_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    warnings: Iterable[str] = (),
    limit: int = 30,
) -> str:
    items = [dict(row) for row in rows if isinstance(row, Mapping)]
    lane_counts = _counts(row.get("opportunity_type") for row in items)
    type_counts = _counts(row.get("event_type") for row in items)
    lines = [
        "# Event Alpha Scheduled Catalyst Report",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        f"Profile: {profile or 'unknown'}",
        f"Artifact namespace: {artifact_namespace or 'unknown'}",
        f"Scheduled catalysts: {len(items)}",
        "Event types: " + (_format_counts(type_counts) or "none"),
        "Opportunity lanes: " + (_format_counts(lane_counts) or "none"),
        "",
        "## Upcoming Scheduled Catalysts",
    ]
    if not items:
        lines.append("- None.")
    for row in sorted(items, key=lambda item: (str(item.get("event_start_time") or ""), str(item.get("title") or "")))[: max(0, limit)]:
        lines.append(
            "- "
            f"{row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'} "
            f"{row.get('event_type') or 'unknown'} "
            f"status={row.get('event_status') or 'unknown'} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'} "
            f"source_class={row.get('source_class') or 'unknown'}"
        )
        lines.append(f"  timing: start={row.get('event_start_time') or 'unknown'}")
        if row.get("why_not_alertable"):
            lines.append("  why_not_alertable: " + "; ".join(str(item) for item in row.get("why_not_alertable") or ()))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
    warning_rows = [str(item) for item in warnings if str(item)]
    if warning_rows:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in warning_rows[:10])
    return "\n".join(lines) + "\n"


def format_unlock_risk_report(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None = None,
    artifact_namespace: str | None = None,
    warnings: Iterable[str] = (),
    limit: int = 30,
) -> str:
    items = [dict(row) for row in rows if isinstance(row, Mapping)]
    lane_counts = _counts(row.get("opportunity_type") for row in items)
    lines = [
        "# Event Alpha Unlock / Supply Risk Report",
        "",
        "Research-only. Not a trade signal, paper trade, live RSI signal, or execution.",
        f"Profile: {profile or 'unknown'}",
        f"Artifact namespace: {artifact_namespace or 'unknown'}",
        f"Unlock candidates: {len(items)}",
        "Opportunity lanes: " + (_format_counts(lane_counts) or "none"),
        "",
        "## Unlock / Supply Risk",
    ]
    if not items:
        lines.append("- None.")
    for row in sorted(items, key=lambda item: (str(item.get("unlock_time") or ""), str(item.get("symbol") or "")))[: max(0, limit)]:
        lines.append(
            "- "
            f"{row.get('symbol') or 'UNRESOLVED'}/{row.get('coin_id') or 'unresolved'} "
            f"{row.get('unlock_type') or 'unknown'} "
            f"vesting={row.get('vesting_category') or 'unknown'} "
            f"timestamp_confidence={row.get('event_timestamp_confidence') or 'unknown'} "
            f"unlock_pct_circ={_format_pct(row.get('unlock_pct_circulating_supply'))} "
            f"unlock_value_to_mcap={_format_percent_points(row.get('unlock_value_to_market_cap_pct'))} "
            f"unlock_vs_adv={_format_float(row.get('unlock_vs_30d_adv'))} "
            f"lane={row.get('opportunity_type') or 'unknown'} "
            f"market_state={row.get('market_state') or 'unknown'}"
        )
        lines.append(f"  unlock_time: {row.get('unlock_time') or 'unknown'}")
        if row.get("why_not_alertable"):
            lines.append("  why_not_alertable: " + "; ".join(str(item) for item in row.get("why_not_alertable") or ()))
        if row.get("source_url"):
            lines.append(f"  source: {row.get('source_url')}")
    warning_rows = [str(item) for item in warnings if str(item)]
    if warning_rows:
        lines.extend(["", "## Warnings"])
        lines.extend(f"- {warning}" for warning in warning_rows[:10])
    return "\n".join(lines) + "\n"


def _unlock_candidate_for_event(event: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    source_class = str(event.get("source_class") or "").strip()
    source_url = str(event.get("source_url") or "").strip()
    unlock_time = str(event.get("event_start_time") or "").strip()
    pct_circ = _optional_float(_first(item, "unlock_pct_circulating_supply", "unlock_pct_circulating", "percent_of_circulating_supply"))
    pct_total = _optional_float(_first(item, "unlock_pct_total_supply", "percent_of_total_supply"))
    unlock_vs_adv = _optional_float(_first(item, "unlock_vs_30d_adv", "unlock_to_adv", "unlock_vs_adv"))
    value_to_market_cap = _optional_float(item.get("unlock_value_to_market_cap_pct"))
    size_missing = pct_circ is None and pct_total is None and unlock_vs_adv is None and value_to_market_cap is None
    structured = _structured_unlock_proof(source_class, item, event)
    reason_codes = list(event.get("reason_codes") or ())
    if structured:
        reason_codes.append("structured_unlock_evidence")
    else:
        reason_codes.append("structured_unlock_source_required")
    if pct_circ is not None and pct_circ >= 0.05:
        reason_codes.append("material_unlock")
    if unlock_vs_adv is not None and unlock_vs_adv >= 1.0:
        reason_codes.append("unlock_vs_adv_high")
    reaction = event_market_reaction.evaluate_market_reaction({
        **event,
        "source_pack": "unlock_supply_pack",
        "impact_path_type": "unlock_supply_event",
        "source_class": source_class,
        "evidence_quality_score": 92.0 if structured else 45.0,
        "accepted_evidence_count": 1 if structured else 0,
        "accepted_evidence_reason_codes": reason_codes,
        "market_state_snapshot": None,
        "market_snapshot": _market_snapshot(item),
        "derivatives_snapshot": _derivatives_snapshot(item),
        "supply_snapshot": _supply_snapshot(item),
        "negative_catalyst": True,
        "catalyst_fresh": True,
    })
    lane = reaction.opportunity_type
    why_not = list(reaction.why_not_alertable)
    warnings: list[str] = []
    if not structured:
        lane = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
        why_not.append("structured_unlock_proof_missing")
        warnings.append("unlock_supply_event_requires_structured_unlock_source")
    if not unlock_time:
        why_not.append("unlock_time_missing")
        warnings.append("unlock_time_missing")
        lane = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    if not source_url:
        why_not.append("source_url_missing")
        warnings.append("unlock_source_url_missing")
        lane = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
    if size_missing and lane in {
        event_market_reaction.EventOpportunityType.RISK_ONLY.value,
        event_market_reaction.EventOpportunityType.FADE_SHORT_REVIEW.value,
    }:
        lane = event_market_reaction.EventOpportunityType.UNCONFIRMED_RESEARCH.value
        why_not.append("unlock_size_metrics_missing")
    return {
        "schema_version": 1,
        "row_type": "unlock_event",
        "profile": event.get("profile"),
        "artifact_namespace": event.get("artifact_namespace"),
        "run_mode": event.get("run_mode"),
        "run_id": event.get("run_id"),
        "unlock_candidate_id": f"unl:{event.get('provider')}:{_digest(str(event.get('event_id')) + '|' + str(event.get('symbol')))}",
        "scheduled_catalyst_id": event.get("scheduled_catalyst_id"),
        "symbol": event.get("symbol"),
        "coin_id": event.get("coin_id"),
        "validated_symbol": event.get("validated_symbol"),
        "validated_coin_id": event.get("validated_coin_id"),
        "event_name": event.get("event_name"),
        "event_type": "token_unlock",
        "impact_path_type": "unlock_supply_event",
        "source_pack": "unlock_supply_pack",
        "source_class": source_class,
        "source_strength": event.get("source_strength"),
        "source_provider": event.get("provider"),
        "source_url": event.get("source_url"),
        "unlock_time": unlock_time or None,
        "unlock_type": _unlock_type(item),
        "cliff_or_linear": _cliff_or_linear(item),
        "tokens_unlocked": _optional_float(_first(item, "tokens_unlocked", "unlock_amount", "amount")),
        "unlock_usd": _optional_float(_first(item, "unlock_usd", "unlock_value_usd", "value_usd")),
        "unlock_value_to_market_cap_pct": value_to_market_cap,
        "unlock_value_to_market_cap_unit": str(item.get("unlock_value_to_market_cap_unit") or "").strip() or None,
        "unlock_pct_circulating_supply": pct_circ,
        "unlock_pct_circulating": pct_circ,
        "unlock_pct_total_supply": pct_total,
        "unlock_vs_30d_adv": unlock_vs_adv,
        "vesting_category": _vesting_category(item),
        "recipient_category": _vesting_category(item),
        "event_timestamp_confidence": event.get("event_timestamp_confidence"),
        "source_confidence": event.get("confidence"),
        "confidence": event.get("confidence"),
        "reason_codes": tuple(dict.fromkeys(reason_codes)),
        "structured_unlock_evidence": structured,
        "market_snapshot": _market_snapshot(item),
        "derivatives_snapshot": _derivatives_snapshot(item),
        "supply_snapshot": _supply_snapshot(item),
        "provider_api_version": event.get("provider_api_version"),
        "provider_query_at": event.get("provider_query_at"),
        "acquired_at": event.get("acquired_at"),
        "provider_snapshot_status": event.get("provider_snapshot_status"),
        "source_coverage_complete": event.get("source_coverage_complete"),
        "capture_mode": event.get("capture_mode"),
        "fixture_provenance": event.get("fixture_provenance"),
        "authority_eligible": event.get("authority_eligible"),
        "protocol_v2_evidence_eligible": event.get("protocol_v2_evidence_eligible"),
        "first_public_at": event.get("first_public_at"),
        "first_public_at_status": event.get("first_public_at_status"),
        "field_units": dict(event.get("field_units") or {}) if isinstance(event.get("field_units"), Mapping) else {},
        "market_state_snapshot": reaction.market_state_snapshot.to_dict(),
        "market_state": reaction.market_state,
        "opportunity_type": lane,
        "source_requirements_met": bool(structured),
        "market_requirements_met": reaction.market_requirements_met,
        "fade_requirements_met": reaction.fade_requirements_met,
        "why_now": reaction.why_now,
        "what_confirms": reaction.what_confirms,
        "what_invalidates": reaction.what_invalidates,
        "why_not_alertable": tuple(dict.fromkeys(why_not)),
        "warnings": tuple(dict.fromkeys(warnings)),
        "research_only": True,
        "created_alert": False,
        "notification_send_enabled": False,
    }


def _load_tokenomist_items(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    source = Path(path).expanduser()
    if not source.exists():
        return ()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if tokenomist_v5.is_tokenomist_v5_fixture_capture(raw):
        return tokenomist_v5.normalize_tokenomist_v5_fixture_capture(raw)
    return _items_from_raw(raw, "unlocks")


def _load_messari_unlock_items(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    return _load_items(path, "unlocks")


def _load_calendar_items(path: str | Path) -> tuple[Mapping[str, Any], ...]:
    return _load_items(path, "events")


def _normalize_messari_unlock_item(item: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(item)
    asset = out.get("asset")
    if isinstance(asset, Mapping):
        out.setdefault("token_id", asset.get("id"))
        out.setdefault("token_name", asset.get("name"))
        out.setdefault("token_symbol", asset.get("symbol"))
        out.setdefault("coin_id", asset.get("id"))
        out.setdefault("symbol", asset.get("symbol"))
    out.setdefault("unlock_date", out.get("timestamp") or out.get("unlock_at") or out.get("event_time"))
    out.setdefault("source_class", "structured_unlock")
    out.setdefault("event_type", "token_unlock")
    return out


def _load_items(path: str | Path, key: str) -> tuple[Mapping[str, Any], ...]:
    source = Path(path).expanduser()
    if not source.exists():
        return ()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return ()
    return _items_from_raw(raw, key)


def _items_from_raw(raw: object, key: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(raw, Mapping):
        raw_items = raw.get(key) or raw.get("items") or raw.get("data") or []
    else:
        raw_items = raw
    if not isinstance(raw_items, Iterable) or isinstance(raw_items, (str, bytes, Mapping)):
        return ()
    return tuple(dict(item) for item in raw_items if isinstance(item, Mapping))


def _load_rows(path: str | Path | None, filename: str, row_type: str) -> list[dict[str, Any]]:
    if path is None:
        return []
    source = Path(path).expanduser()
    if source.is_dir():
        source = source / filename
    if not source.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, Mapping) and row.get("row_type") == row_type:
            out.append(dict(row))
    return out


def _jsonl_bytes(path: Path, rows: Iterable[Mapping[str, Any]]) -> bytes:
    lines = []
    for row in rows:
        stamped = schema_v1.stamp_artifact_row(row, path=path)
        lines.append(
            json.dumps(
                _json_ready(stamped),
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        )
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _title(item: Mapping[str, Any]) -> str:
    return str(item.get("title") or item.get("name") or item.get("headline") or "").strip()


def _description(item: Mapping[str, Any]) -> str:
    return str(item.get("description_summary") or item.get("description") or item.get("body") or item.get("summary") or "").strip()


def _event_time(item: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        parsed = _parse_time(item.get(key))
        if parsed is not None:
            return parsed.isoformat()
    return None


def _parse_time(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, bool):
        raise ValueError(f"invalid datetime {value!r}")
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValueError(f"invalid datetime {value!r}")
        seconds = numeric / 1000.0 if numeric > 10_000_000_000 else numeric
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OSError, OverflowError, ValueError) as exc:
            raise ValueError(f"invalid datetime {value!r}") from exc
    return parse_datetime(value)


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _event_age_hours(event_time: str | None, observed: datetime) -> float | None:
    parsed = _parse_time(event_time)
    if parsed is None:
        return None
    return round((observed - parsed).total_seconds() / 3600.0, 4)


def _event_status(item: Mapping[str, Any]) -> str:
    raw = str(item.get("event_status") or item.get("status") or "").strip().casefold()
    if raw in {"confirmed", "tentative", "rumored", "completed", "canceled", "cancelled"}:
        return "canceled" if raw == "cancelled" else raw
    if item.get("cancelled") is True or item.get("canceled") is True:
        return "canceled"
    if item.get("rumored") is True or str(item.get("certainty") or "").casefold() == "rumor":
        return "rumored"
    if item.get("confirmed") is False:
        return "rumored"
    return "confirmed"


def _asset_identity(item: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    symbols: list[str] = []
    coin_ids: list[str] = []
    symbol = item.get("symbol") or item.get("token_symbol")
    coin_id = item.get("coin_id") or item.get("token_id")
    if symbol:
        symbols.append(str(symbol).upper().strip())
    if coin_id:
        coin_ids.append(str(coin_id).strip())
    coins = item.get("coins")
    if isinstance(coins, Iterable) and not isinstance(coins, (str, bytes, Mapping)):
        for coin in coins:
            if not isinstance(coin, Mapping):
                continue
            if coin.get("symbol"):
                symbols.append(str(coin.get("symbol")).upper().strip())
            if coin.get("id"):
                coin_ids.append(str(coin.get("id")).strip())
    return tuple(dict.fromkeys(item for item in symbols if item)), tuple(dict.fromkeys(item for item in coin_ids if item))


def _calendar_event_type(item: Mapping[str, Any]) -> str:
    explicit = str(item.get("event_type") or "").strip().casefold()
    if explicit:
        return _normalize_event_type(explicit)
    text = " ".join(str(value or "") for value in (item.get("title"), item.get("description"), item.get("categories"))).casefold()
    if "unlock" in text or "vesting" in text or "emission" in text:
        return "token_unlock"
    if "governance" in text or "vote" in text:
        return "governance_vote"
    if "upgrade" in text:
        return "protocol_upgrade"
    if "mainnet" in text:
        return "mainnet"
    if "testnet" in text:
        return "testnet"
    if "airdrop" in text:
        return "airdrop"
    if "staking" in text or "reward" in text:
        return "staking_reward"
    return "other"


def _unlock_event_type(item: Mapping[str, Any]) -> str:
    kind = str(item.get("unlock_type") or item.get("type") or "").casefold()
    if "linear" in kind:
        return "linear_emission"
    if "emission" in kind:
        return "linear_emission"
    if "cliff" in kind or "vesting" in kind:
        return "vesting_cliff"
    return "token_unlock"


def _normalize_event_type(value: str) -> str:
    clean = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "unlock": "token_unlock",
        "token_unlock": "token_unlock",
        "vesting": "vesting_cliff",
        "vesting_cliff": "vesting_cliff",
        "linear_emission": "linear_emission",
        "emission": "linear_emission",
        "governance": "governance_vote",
        "governance_vote": "governance_vote",
        "protocol_upgrade": "protocol_upgrade",
        "upgrade": "protocol_upgrade",
        "mainnet_launch": "mainnet",
        "mainnet": "mainnet",
        "testnet": "testnet",
        "airdrop": "airdrop",
        "staking_reward": "staking_reward",
    }
    return aliases.get(clean, "other")


def _unlock_type(item: Mapping[str, Any]) -> str:
    event_type = _unlock_event_type(item)
    if event_type == "vesting_cliff":
        return "cliff"
    if event_type == "linear_emission":
        return "linear"
    raw = str(item.get("unlock_type") or "").casefold()
    if raw in {"cliff", "linear", "emission", "unknown"}:
        return raw
    return "unknown"


def _cliff_or_linear(item: Mapping[str, Any]) -> str:
    unlock_type = _unlock_type(item)
    if unlock_type in {"cliff", "linear"}:
        return unlock_type
    return "unknown"


def _vesting_category(item: Mapping[str, Any]) -> str | None:
    return _first_text(item, "vesting_category", "recipient_category", "allocation_category", "allocation", "category")


def _event_timestamp_confidence(
    item: Mapping[str, Any],
    *,
    event_start: str | None,
    source_class: str,
) -> str:
    raw = _first_text(item, "event_timestamp_confidence", "event_time_confidence", "timestamp_confidence", "time_confidence")
    if raw:
        clean = raw.strip().casefold().replace("-", "_").replace(" ", "_")
        if clean in {"confirmed", "high", "exact"}:
            return "confirmed"
        if clean in {"estimated", "medium", "approximate", "date_only"}:
            return "estimated"
        if clean in {"low", "unknown", "missing"}:
            return "unknown"
        return clean
    if not event_start:
        return "unknown"
    if source_class in {"structured_unlock", "structured_calendar", "official_project", "official_exchange", "supply_data"}:
        return "confirmed"
    return "estimated"


def _source_class_for_provider(provider: str) -> str:
    text = str(provider or "").casefold()
    if "tokenomist" in text or "messari" in text or "unlock" in text:
        return "structured_unlock"
    if "coinmarketcal" in text or "coindar" in text or "calendar" in text:
        return "structured_calendar"
    return "media_calendar"


def _source_strength(source_class: str, status: str) -> str:
    if status in {"rumored", "canceled"}:
        return "weak"
    if source_class in {"structured_unlock", "structured_calendar", "official_project", "official_exchange", "supply_data"}:
        return "official_structured"
    return "medium" if source_class == "media_calendar" else "weak"


def _confidence(item: Mapping[str, Any], *, source_class: str, status: str, event_start: str | None, symbols: tuple[str, ...]) -> float:
    try:
        base = float(item.get("confidence") or item.get("source_confidence") or 0.82)
    except (TypeError, ValueError):
        base = 0.82
    if source_class in {"structured_unlock", "official_project", "official_exchange"}:
        base = max(base, 0.90)
    if source_class == "structured_calendar":
        base = max(base, 0.84)
    if status == "rumored":
        base = min(base, 0.60)
    if status == "canceled":
        base = min(base, 0.50)
    if not event_start:
        base -= 0.25
    if not symbols:
        base -= 0.15
    return round(max(0.10, min(0.98, base)), 2)


def _scheduled_reason_codes(
    *,
    event_type: str,
    source_class: str,
    event_start: str | None,
    source_url: str | None,
    symbols: tuple[str, ...],
    coin_ids: tuple[str, ...],
    item: Mapping[str, Any],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if source_class == "structured_unlock":
        reasons.append("structured_unlock_source")
    if source_class == "structured_calendar":
        reasons.append("structured_calendar_source")
    if source_class == "official_project":
        reasons.append("official_project_source")
    if event_start:
        reasons.append("event_time_confirmation")
    if source_url:
        reasons.append("source_url_present")
    if symbols or coin_ids:
        reasons.append("token_identity")
    if event_type in POSITIVE_EVENT_TYPES:
        reasons.append("direct_project_event")
    if event_type in {"token_unlock", "vesting_cliff", "linear_emission"}:
        reasons.append("direct_token_unlock_fact")
    pct = _optional_float(_first(item, "unlock_pct_circulating_supply", "unlock_pct_circulating", "percent_of_circulating_supply"))
    if pct is not None and pct >= 0.05:
        reasons.append("material_unlock")
    return tuple(dict.fromkeys(reasons))


def _source_pack_for_event_type(event_type: str) -> str:
    if event_type in {"token_unlock", "vesting_cliff", "linear_emission"}:
        return "unlock_supply_pack"
    return "project_event_pack"


def _impact_path_for_event_type(event_type: str) -> str:
    if event_type in {"token_unlock", "vesting_cliff", "linear_emission"}:
        return "unlock_supply_event"
    if event_type in {"protocol_upgrade", "mainnet", "testnet"}:
        return "direct_protocol_event"
    if event_type in {"airdrop", "staking_reward"}:
        return "direct_token_event"
    return "project_event"


def _structured_calendar_or_official(row: Mapping[str, Any]) -> bool:
    return str(row.get("source_class") or "") in STRUCTURED_CALENDAR_CLASSES | STRUCTURED_UNLOCK_CLASSES


def _structured_unlock_proof(source_class: str, item: Mapping[str, Any], event: Mapping[str, Any]) -> bool:
    if source_class in STRUCTURED_UNLOCK_CLASSES:
        return True
    if source_class == TRUSTED_CALENDAR_UNLOCK_CLASS and str(event.get("event_type") or "") == "token_unlock":
        return bool(event.get("event_start_time") and event.get("source_url") and (
            _optional_float(_first(item, "unlock_pct_circulating_supply", "unlock_pct_circulating", "percent_of_circulating_supply")) is not None
            or _optional_float(_first(item, "tokens_unlocked", "unlock_amount")) is not None
        ))
    return False


def _stale_completed(row: Mapping[str, Any]) -> bool:
    if str(row.get("event_status") or "") != "completed":
        return False
    age = _optional_float(row.get("event_age_hours"))
    return age is not None and age > 24


def _catalyst_fresh(row: Mapping[str, Any]) -> bool:
    if str(row.get("event_status") or "") in {"rumored", "canceled"}:
        return False
    age = _optional_float(row.get("event_age_hours"))
    if age is None:
        return False
    return -168 <= age <= 24


def _market_snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
    market = item.get("market_snapshot") or item.get("market") or {}
    return dict(market) if isinstance(market, Mapping) else {}


def _derivatives_snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
    derivatives = item.get("derivatives_snapshot") or item.get("derivatives") or {}
    return dict(derivatives) if isinstance(derivatives, Mapping) else {}


def _supply_snapshot(item: Mapping[str, Any]) -> dict[str, Any]:
    supply = item.get("supply_snapshot") or item.get("supply") or {}
    if isinstance(supply, Mapping):
        return dict(supply)
    out: dict[str, Any] = {}
    for key in (
        "unlock_pct_circulating",
        "unlock_pct_circulating_supply",
        "unlock_amount",
        "unlock_usd",
        "unlock_value_to_market_cap_pct",
        "unlock_value_to_market_cap_unit",
        "unlock_vs_30d_adv",
        "field_units",
    ):
        if item.get(key) not in (None, ""):
            out[key] = item.get(key)
    return out


def _first(item: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _first_text(item: Mapping[str, Any], *keys: str) -> str | None:
    value = _first(item, *keys)
    text = str(value or "").strip()
    return text or None


def _optional_float(value: object) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _format_pct(value: object) -> str:
    parsed = _optional_float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) <= 3.0:
        parsed *= 100.0
    return f"{parsed:.1f}%"


def _format_float(value: object) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.2f}"


def _format_percent_points(value: object) -> str:
    parsed = _optional_float(value)
    return "n/a" if parsed is None else f"{parsed:.2f}% mcap"


def _redacted_payload(item: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in item.items():
        clean_key = str(key)
        if any(secret_word in clean_key.casefold() for secret_word in ("token", "secret", "apikey", "api_key", "signature")):
            out[clean_key] = "<redacted>"
        else:
            out[clean_key] = value
    return out


def _digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _counts(values: Iterable[object]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value or "unknown")
        out[key] = out.get(key, 0) + 1
    return out


def _format_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()) if value)


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()
