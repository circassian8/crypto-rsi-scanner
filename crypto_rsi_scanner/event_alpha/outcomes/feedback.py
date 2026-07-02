# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_eval_export.py
# ---------------------------------------------------------------------------
"""Export proposed Event Alpha eval cases from feedback and missed artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class EventAlphaEvalExportResult:
    out_dir: Path
    files_written: tuple[Path, ...]
    proposed_cases: int
    source: str


def export_cases_from_feedback(
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    out_dir: str | Path,
    *,
    now: datetime | None = None,
) -> EventAlphaEvalExportResult:
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    by_key = {str(row.get("alert_key") or row.get("key") or ""): row for row in alerts}
    cases: list[dict[str, Any]] = []
    for row in feedback:
        if row.get("label") not in {"junk", "useful", "watch"}:
            continue
        alert = by_key.get(str(row.get("key") or row.get("target") or ""))
        if not alert:
            continue
        cases.append(_feedback_case(alert, row))
    return _write_cases(out_dir, {"proposed_llm_golden_cases.json": cases}, "feedback", now=now)


def export_cases_from_missed(
    missed_rows: Iterable[Mapping[str, Any]],
    out_dir: str | Path,
    *,
    now: datetime | None = None,
) -> EventAlphaEvalExportResult:
    extraction_cases: list[dict[str, Any]] = []
    alpha_cases: list[dict[str, Any]] = []
    for row in missed_rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("failure_stage") == "resolver_missed_asset":
            extraction_cases.append(_missed_extraction_case(row))
        alpha_cases.append(_missed_alpha_case(row))
    return _write_cases(
        out_dir,
        {
            "proposed_llm_extraction_golden_cases.json": extraction_cases,
            "proposed_event_alpha_golden_cases.json": alpha_cases,
        },
        "missed",
        now=now,
    )


def format_eval_export_result(result: EventAlphaEvalExportResult) -> str:
    return "\n".join([
        "=" * 76,
        "EVENT ALPHA PROPOSED EVAL CASES EXPORTED (research-only)",
        "=" * 76,
        f"source: {result.source}",
        f"out_dir: {result.out_dir}",
        f"files_written: {len(result.files_written)} · proposed_cases={result.proposed_cases}",
        *(f"- {path}" for path in result.files_written),
        "Canonical fixtures were not modified.",
    ])


def _feedback_case(alert: Mapping[str, Any], feedback: Mapping[str, Any]) -> dict[str, Any]:
    label = str(feedback.get("label") or "")
    expected_role = "source_noise" if label == "junk" else str(alert.get("llm_asset_role") or alert.get("asset_role") or "ambiguous")
    expected_action = "store_only" if label == "junk" else str(alert.get("tier") or "radar_digest").lower()
    return _redact({
        "case_id": f"feedback_{alert.get('alert_key') or alert.get('snapshot_id')}",
        "source": "feedback_export",
        "label": label,
        "title": alert.get("event_name"),
        "body": alert.get("reason"),
        "source_url": alert.get("source_url"),
        "symbol": alert.get("asset_symbol"),
        "coin_id": alert.get("asset_coin_id"),
        "expected_asset_role": expected_role,
        "expected_relationship_type": alert.get("llm_relationship_type") or alert.get("relationship_type"),
        "expected_recommended_alert_action": expected_action,
        "feedback_notes": feedback.get("notes"),
    })


def _missed_extraction_case(row: Mapping[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "")
    name = str(row.get("name") or row.get("coin_id") or symbol)
    return _redact({
        "case_id": f"missed_extraction_{symbol or row.get('coin_id')}",
        "source": "missed_export",
        "title": f"{name} missed opportunity follow-up",
        "body": row.get("reason"),
        "expected_crypto_asset_mentions": [{
            "symbol": symbol,
            "coin_id": row.get("coin_id"),
            "name": name,
            "mention_type": "project_or_token",
        }],
        "suggested_queries": list(row.get("suggested_queries") or []),
    })


def _missed_alpha_case(row: Mapping[str, Any]) -> dict[str, Any]:
    return _redact({
        "case_id": f"missed_alpha_{row.get('symbol') or row.get('coin_id')}_{row.get('move_window')}",
        "source": "missed_export",
        "symbol": row.get("symbol"),
        "coin_id": row.get("coin_id"),
        "move_window": row.get("move_window"),
        "return_pct": row.get("return_pct"),
        "expected_failure_stage": row.get("failure_stage"),
        "suggested_queries": list(row.get("suggested_queries") or []),
    })


def _write_cases(
    out_dir: str | Path,
    files: Mapping[str, list[dict[str, Any]]],
    source: str,
    *,
    now: datetime | None,
) -> EventAlphaEvalExportResult:
    target = Path(out_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    generated = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    written: list[Path] = []
    total = 0
    for filename, cases in files.items():
        payload = {
            "schema_version": "event_alpha_proposed_eval_cases_v1",
            "generated_at": generated,
            "source": source,
            "cases": cases,
        }
        path = target / filename
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
        total += len(cases)
    return EventAlphaEvalExportResult(target, tuple(written), total, source)


def _redact(row: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        text = str(value)
        if "OPENAI_API_KEY" in text or "TELEGRAM_BOT_TOKEN" in text or ".env" in text:
            out[str(key)] = "[redacted]"
        else:
            out[str(key)] = value
    return out


# ---------------------------------------------------------------------------
# Moved from crypto_rsi_scanner/event_alpha_feedback_readiness.py
# ---------------------------------------------------------------------------
"""Feedback-loop readiness checks for Event Alpha research artifacts."""


from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from ... import (
    event_alpha_alert_store,
    event_alpha_router,
    event_watchlist,
)
from ..artifacts import research_cards as event_research_cards
from ..notifications import inbox as event_alpha_notification_inbox
from ..radar import core_opportunities as event_core_opportunities


@dataclass(frozen=True)
class EventAlphaFeedbackReadinessResult:
    profile: str
    artifact_namespace: str
    cards_checked: int
    cards_with_lineage: int
    cards_with_feedback_target: int
    core_opportunity_cards_ready: int
    near_miss_cards_ready: int
    local_only_cards_ready: int
    alert_rows_checked: int
    alert_rows_with_feedback_targets: int
    alert_rows_core_reconciled: int = 0
    stale_snapshot_routes_capped: int = 0
    snapshots_missing_core_store: int = 0
    inbox_review_items: int = 0
    feedback_rows: int = 0
    calibration_ready_rows: int = 0
    visible_core_opportunities: int = 0
    visible_core_opportunities_with_cards: int = 0
    visible_core_opportunities_with_feedback_targets: int = 0
    visible_core_opportunities_missing_cards: int = 0
    visible_core_opportunities_missing_feedback_targets: int = 0
    canonical_review_items: int = 0
    canonical_review_items_with_cards: int = 0
    canonical_review_items_with_feedback_targets: int = 0
    diagnostic_review_items_hidden: int = 0
    diagnostic_review_items_with_feedback_targets: int = 0
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.blockers


def build_feedback_readiness(
    *,
    profile: str,
    artifact_namespace: str,
    card_paths: Iterable[str | Path],
    alert_rows: Iterable[Mapping[str, Any]],
    feedback_rows: Iterable[Mapping[str, Any]],
    watchlist_entries: Iterable[event_watchlist.EventWatchlistEntry],
    core_opportunity_rows: Iterable[Mapping[str, Any]] = (),
    inbox_result: event_alpha_notification_inbox.EventAlphaNotificationInboxResult | None = None,
) -> EventAlphaFeedbackReadinessResult:
    """Check whether local artifacts are ready for manual useful/junk feedback."""
    cards = [Path(path) for path in card_paths]
    alerts = [dict(row) for row in alert_rows if isinstance(row, Mapping)]
    feedback = [dict(row) for row in feedback_rows if isinstance(row, Mapping)]
    entries = list(watchlist_entries)
    core_rows = [dict(row) for row in core_opportunity_rows if isinstance(row, Mapping)]
    research_cards = [path for path in cards if path.name != "index.md"]
    card_core_ids = {value for path in research_cards for value in (event_research_cards.card_core_opportunity_id(path),) if value}
    card_feedback_targets = {value for path in research_cards for value in (event_research_cards.card_feedback_target(path),) if value}
    cards_with_lineage = sum(1 for path in research_cards if event_research_cards.card_has_current_lineage(path))
    cards_with_target = sum(1 for path in research_cards if event_research_cards.card_feedback_target(path))
    ready_by_group = _ready_card_groups(research_cards)
    required_alerts = [row for row in alerts if not event_alpha_notification_inbox.alert_snapshot_is_diagnostic(row)]
    alert_targets = sum(1 for row in required_alerts if _alert_has_feedback_target(row))
    alert_core_reconciled = sum(1 for row in alerts if bool(row.get("snapshot_core_reconciled")))
    stale_snapshot_routes_capped = sum(1 for row in alerts if _snapshot_route_was_capped_by_core(row))
    snapshots_missing_core = sum(
        1 for row in alerts
        if str(row.get("core_resolution_status") or row.get("snapshot_core_resolution_status") or "") == event_alpha_alert_store.SNAPSHOT_MISSING_CORE
    )
    calibration_ready = sum(1 for row in [*alerts, *(_entry_row(entry) for entry in entries)] if _row_has_calibration_fields(row))
    inbox_items = _inbox_review_count(inbox_result)
    canonical_review_items = (
        len(inbox_result.canonical_review_items)
        if inbox_result is not None
        else 0
    )
    canonical_review_items_with_cards = (
        inbox_result.canonical_review_items_with_cards
        if inbox_result is not None
        else 0
    )
    canonical_review_items_with_targets = (
        inbox_result.canonical_review_items_with_feedback_targets
        if inbox_result is not None
        else 0
    )
    diagnostic_review_items_hidden = (
        len(inbox_result.diagnostic_review_items_hidden)
        if inbox_result is not None
        else 0
    )
    diagnostic_review_items_with_targets = (
        inbox_result.diagnostic_review_items_with_feedback_targets
        if inbox_result is not None
        else 0
    )
    visible_core = event_core_opportunities.visible_core_opportunities(core_rows or [*entries, *alerts])
    alert_core_targets = {
        str(row.get("core_opportunity_id") or "")
        for row in alerts
        if str(row.get("core_opportunity_id") or "")
    }
    alert_feedback_targets = {
        str(row.get("feedback_target") or "")
        for row in alerts
        if str(row.get("feedback_target") or "")
    }
    visible_with_cards = sum(1 for item in visible_core if item.core_opportunity_id in card_core_ids)
    visible_with_targets = sum(
        1
        for item in visible_core
        if item.core_opportunity_id in card_feedback_targets
        or item.core_opportunity_id in alert_core_targets
        or item.core_opportunity_id in alert_feedback_targets
    )
    missing_cards = max(0, len(visible_core) - visible_with_cards)
    missing_targets = max(0, len(visible_core) - visible_with_targets)
    blockers: list[str] = []
    warnings: list[str] = []
    if research_cards and cards_with_lineage < len(research_cards):
        blockers.append("research_cards_missing_lineage")
    if research_cards and cards_with_target < len(research_cards):
        blockers.append("research_cards_missing_feedback_target")
    if required_alerts and alert_targets < len(required_alerts):
        blockers.append("alert_snapshots_missing_feedback_targets")
    if canonical_review_items and canonical_review_items_with_cards < canonical_review_items:
        blockers.append("canonical_review_items_missing_cards")
    if canonical_review_items and canonical_review_items_with_targets < canonical_review_items:
        blockers.append("canonical_review_items_missing_feedback_targets")
    if missing_cards:
        blockers.append("visible_core_opportunities_missing_cards")
    if missing_targets:
        blockers.append("visible_core_opportunities_missing_feedback_targets")
    if inbox_result is not None and inbox_items <= 0 and (alerts or cards):
        warnings.append("inbox_has_no_review_items")
    if alerts and calibration_ready <= 0:
        blockers.append("calibration_fields_missing")
    if not research_cards:
        warnings.append("no_research_cards_found")
    if not alerts:
        warnings.append("no_alert_snapshots_found")
    return EventAlphaFeedbackReadinessResult(
        profile=str(profile or "default"),
        artifact_namespace=str(artifact_namespace or "default"),
        cards_checked=len(research_cards),
        cards_with_lineage=cards_with_lineage,
        cards_with_feedback_target=cards_with_target,
        core_opportunity_cards_ready=ready_by_group.get("Core Opportunity Cards", 0),
        near_miss_cards_ready=ready_by_group.get("Near-Miss Cards", 0),
        local_only_cards_ready=ready_by_group.get("Local-Only / Quality-Capped Cards", 0),
        alert_rows_checked=len(required_alerts),
        alert_rows_with_feedback_targets=alert_targets,
        alert_rows_core_reconciled=alert_core_reconciled,
        stale_snapshot_routes_capped=stale_snapshot_routes_capped,
        snapshots_missing_core_store=snapshots_missing_core,
        inbox_review_items=inbox_items,
        feedback_rows=len(feedback),
        calibration_ready_rows=calibration_ready,
        visible_core_opportunities=len(visible_core),
        visible_core_opportunities_with_cards=visible_with_cards,
        visible_core_opportunities_with_feedback_targets=visible_with_targets,
        visible_core_opportunities_missing_cards=missing_cards,
        visible_core_opportunities_missing_feedback_targets=missing_targets,
        canonical_review_items=canonical_review_items,
        canonical_review_items_with_cards=canonical_review_items_with_cards,
        canonical_review_items_with_feedback_targets=canonical_review_items_with_targets,
        diagnostic_review_items_hidden=diagnostic_review_items_hidden,
        diagnostic_review_items_with_feedback_targets=diagnostic_review_items_with_targets,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def format_feedback_readiness(result: EventAlphaFeedbackReadinessResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA FEEDBACK READINESS (research-only)",
        "=" * 76,
        f"profile: {result.profile}",
        f"artifact_namespace: {result.artifact_namespace}",
        f"ready: {str(result.ready).lower()}",
        f"cards_with_lineage: {result.cards_with_lineage}/{result.cards_checked}",
        f"cards_with_feedback_target: {result.cards_with_feedback_target}/{result.cards_checked}",
        (
            "card_groups_ready: "
            f"core={result.core_opportunity_cards_ready}, "
            f"near_miss={result.near_miss_cards_ready}, "
            f"local_only={result.local_only_cards_ready}"
        ),
        f"alert_feedback_targets: {result.alert_rows_with_feedback_targets}/{result.alert_rows_checked}",
        (
            "alert_snapshot_core_reconciliation: "
            f"reconciled={result.alert_rows_core_reconciled}, "
            f"stale_routes_capped={result.stale_snapshot_routes_capped}, "
            f"missing_core={result.snapshots_missing_core_store}"
        ),
        (
            "visible_core_opportunities: "
            f"{result.visible_core_opportunities} "
            f"cards={result.visible_core_opportunities_with_cards}/{result.visible_core_opportunities} "
            f"feedback_targets={result.visible_core_opportunities_with_feedback_targets}/{result.visible_core_opportunities}"
        ),
        (
            "visible_core_missing: "
            f"cards={result.visible_core_opportunities_missing_cards}, "
            f"feedback_targets={result.visible_core_opportunities_missing_feedback_targets}"
        ),
        f"inbox_review_items: {result.inbox_review_items}",
        (
            "canonical_review_items: "
            f"{result.canonical_review_items} "
            f"cards={result.canonical_review_items_with_cards}/{result.canonical_review_items} "
            f"feedback_targets={result.canonical_review_items_with_feedback_targets}/{result.canonical_review_items}"
        ),
        (
            "diagnostic_review_items_hidden: "
            f"{result.diagnostic_review_items_hidden} "
            f"feedback_targets={result.diagnostic_review_items_with_feedback_targets}"
        ),
        f"feedback_rows: {result.feedback_rows}",
        f"calibration_ready_rows: {result.calibration_ready_rows}",
        "blockers: " + (", ".join(result.blockers) if result.blockers else "none"),
        "warnings: " + (", ".join(result.warnings) if result.warnings else "none"),
        "",
        "Checks: card lineage, alert/card feedback targets, inbox review queues, outcome target IDs, and calibration fields.",
        "Artifact-only check; no sends, trades, paper rows, normal RSI rows, or event-fade state were changed.",
    ]
    return "\n".join(lines)

def _ready_card_groups(paths: Iterable[Path]) -> dict[str, int]:
    counts: dict[str, int] = {
        "Core Opportunity Cards": 0,
        "Near-Miss Cards": 0,
        "Local-Only / Quality-Capped Cards": 0,
    }
    for path in paths:
        if not event_research_cards.card_has_current_lineage(path):
            continue
        if not event_research_cards.card_feedback_target(path):
            continue
        group = event_research_cards.card_index_group(path)
        if group in counts:
            counts[group] += 1
    return counts


def _alert_has_feedback_target(row: Mapping[str, Any]) -> bool:
    return any(str(row.get(key) or "").strip() for key in (
        "feedback_target",
        "core_opportunity_id",
        "alert_id",
        "card_id",
        "alert_key",
        "snapshot_id",
    ))


def _row_has_calibration_fields(row: Mapping[str, Any]) -> bool:
    components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else row.get("score_components")
    if not isinstance(components, Mapping):
        components = {}
    return all(
        (row.get(key) not in (None, "", [], {}, ()) or components.get(key) not in (None, "", [], {}, ()))
        for key in ("impact_path_type", "candidate_role", "opportunity_level")
    )


def _entry_row(entry: event_watchlist.EventWatchlistEntry) -> dict[str, Any]:
    return {
        "key": entry.key,
        "impact_path_type": entry.impact_path_type,
        "candidate_role": entry.candidate_role,
        "opportunity_level": entry.opportunity_level,
        "latest_score_components": dict(entry.latest_score_components or {}),
    }


def _inbox_review_count(result: event_alpha_notification_inbox.EventAlphaNotificationInboxResult | None) -> int:
    if result is None:
        return 0
    if result.canonical_review_items:
        return sum(1 for item in result.canonical_review_items if not item.reviewed)
    return sum(len(getattr(result, field)) for field in (
        "sent_without_feedback",
        "partial_delivered_without_feedback",
        "would_send_without_feedback",
        "would_send_blocked_without_feedback",
        "quality_gated_local_only",
        "legacy_quality_conflicts",
        "exploratory_without_feedback",
        "high_priority_unreviewed",
        "triggered_fade_unreviewed",
    ))


def _snapshot_route_was_capped_by_core(row: Mapping[str, Any]) -> bool:
    requested = str(row.get("requested_route_before_core_reconciliation") or "").strip()
    final = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
    return (
        bool(row.get("snapshot_core_reconciled"))
        and event_alpha_router.route_value_is_alertable(requested)
        and not event_alpha_router.route_value_is_alertable(final)
    )
