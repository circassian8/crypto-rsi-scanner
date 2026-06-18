"""Local-artifact replay summaries for Event Alpha Radar research runs."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import (
    event_alerts,
    event_alpha_priors,
    event_alpha_router,
    event_discovery,
    event_llm_analyzer,
    event_watchlist,
)
from .event_models import DiscoveredAsset, RawDiscoveredEvent
from .event_providers.coingecko_universe import assets_from_markets
from .event_providers.manual_json import parse_datetime


@dataclass(frozen=True)
class EventAlphaReplayResult:
    alert_rows: int
    watchlist_rows: int
    raw_events: int = 0
    candidates: int = 0
    alertable_count: int = 0
    priors_enabled: bool = False
    llm_advisory: bool = False
    tier_counts: dict[str, int] | None = None
    tier_counts_with_priors: dict[str, int] | None = None
    route_counts: dict[str, int] | None = None
    score_before_after: tuple[tuple[str, int, int], ...] = ()
    tier_changes: tuple[tuple[str, str, str], ...] = ()
    warnings: tuple[str, ...] = ()


def replay_from_artifacts(
    *,
    alert_rows: Iterable[Mapping[str, Any]] = (),
    watchlist_rows: Iterable[Mapping[str, Any]] = (),
    priors_enabled: bool = False,
    llm_advisory: bool = False,
) -> EventAlphaReplayResult:
    """Summarize a deterministic replay from already-collected artifacts.

    This replay intentionally does not call providers, send alerts, or mutate
    watchlist state. It is a daily debugging tool for comparing local outputs
    across prior/LLM modes.
    """
    alerts = [dict(row) for row in alert_rows]
    watch = [dict(row) for row in watchlist_rows]
    scores: list[tuple[str, int, int]] = []
    for row in alerts:
        before = _int(row.get("score_before_priors") or row.get("opportunity_score"))
        after = _int(row.get("score_after_priors") or row.get("opportunity_score"))
        if priors_enabled or before != after:
            scores.append((str(row.get("alert_key") or row.get("snapshot_id") or row.get("event_id") or ""), before, after))
    return EventAlphaReplayResult(
        alert_rows=len(alerts),
        watchlist_rows=len(watch),
        alertable_count=sum(1 for row in alerts if str(row.get("route") or "").upper() in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "TRIGGERED_FADE_RESEARCH"}),
        priors_enabled=bool(priors_enabled),
        llm_advisory=bool(llm_advisory),
        tier_counts=_counts(alerts, "tier"),
        route_counts=_counts(alerts, "route"),
        score_before_after=tuple(scores[:50]),
        warnings=("local artifacts only; no provider fetches or sends were attempted",),
    )


def replay_from_raw_events(
    *,
    raw_events: Iterable[RawDiscoveredEvent],
    assets: Iterable[DiscoveredAsset],
    market_rows: Iterable[Mapping[str, Any]] = (),
    alert_cfg: event_alerts.EventAlertConfig | None = None,
    priors_cfg: event_alpha_priors.EventAlphaPriorsConfig | None = None,
    llm_provider: object | None = None,
    llm_cfg: event_llm_analyzer.EventLLMConfig | None = None,
    router_cfg: event_alpha_router.EventAlphaRouterConfig | None = None,
    now: datetime | None = None,
) -> EventAlphaReplayResult:
    """Replay raw event evidence through local deterministic Event Alpha stages.

    The harness uses only caller-supplied raw events, assets, market rows, and
    optional fixture/cache LLM output. It writes watchlist state only under a
    temporary directory and never sends alerts or touches live scanner storage.
    """
    observed = _as_utc(now or datetime.now(timezone.utc))
    alert_cfg = alert_cfg or event_alerts.EventAlertConfig()
    market = event_discovery.event_market_enrichment.market_snapshots_from_rows(market_rows, now=observed) if hasattr(event_discovery, "event_market_enrichment") else {}
    discovery = event_discovery.run_discovery(
        tuple(raw_events),
        tuple(assets),
        cfg=event_discovery.EventDiscoveryConfig(),
        now=observed,
        market_by_asset=market,
    )
    baseline = event_alerts.build_event_alert_candidates(discovery, cfg=alert_cfg, now=observed)
    compared = baseline
    warnings = ["local raw replay only; no live providers or sends were attempted"]
    if llm_provider is not None and llm_cfg is not None:
        if str(getattr(llm_cfg, "provider", "")).lower() == "openai":
            warnings.append("LLM replay refused live OpenAI provider; use fixture/cache output")
        else:
            llm_rows = event_llm_analyzer.analyze_event_candidates(discovery, baseline, llm_provider, cfg=llm_cfg)
            compared = event_alerts.apply_llm_advisory(
                baseline,
                llm_rows,
                alert_cfg,
                enabled=llm_cfg.mode == "advisory",
            )
    priors_enabled = bool(priors_cfg and priors_cfg.enabled)
    with_priors = event_alpha_priors.apply_priors_to_alerts(
        compared,
        cfg=priors_cfg or event_alpha_priors.EventAlphaPriorsConfig(enabled=False),
        alert_cfg=alert_cfg,
    )
    with tempfile.TemporaryDirectory(prefix="event-alpha-replay-") as tmp:
        watch_cfg = event_watchlist.EventWatchlistConfig(
            enabled=True,
            state_path=Path(tmp) / "watchlist.jsonl",
        )
        refreshed = event_watchlist.refresh_watchlist(with_priors, cfg=watch_cfg, now=observed)
        read_result = event_watchlist.EventWatchlistReadResult(
            state_path=watch_cfg.state_path or Path(tmp) / "watchlist.jsonl",
            rows_read=len(refreshed.entries),
            entries=refreshed.entries,
            latest_only=True,
        )
        routed = event_alpha_router.route_watchlist(
            read_result,
            cfg=router_cfg or event_alpha_router.EventAlphaRouterConfig(enabled=True),
        )
    baseline_by_key = {_alert_key(alert): alert for alert in baseline}
    prior_scores: list[tuple[str, int, int]] = []
    tier_changes: list[tuple[str, str, str]] = []
    for alert in with_priors:
        before = baseline_by_key.get(_alert_key(alert))
        if before is None:
            continue
        if before.opportunity_score != alert.opportunity_score:
            prior_scores.append((_alert_key(alert), before.opportunity_score, alert.opportunity_score))
        if before.tier != alert.tier:
            tier_changes.append((_alert_key(alert), before.tier.value, alert.tier.value))
    return EventAlphaReplayResult(
        alert_rows=len(with_priors),
        watchlist_rows=len(refreshed.entries),
        raw_events=len(discovery.raw_events),
        candidates=len(discovery.candidates),
        alertable_count=len(routed.alertable_decisions),
        priors_enabled=priors_enabled,
        llm_advisory=bool(llm_provider is not None and llm_cfg is not None and llm_cfg.mode == "advisory"),
        tier_counts=_counts_from_alerts(baseline),
        tier_counts_with_priors=_counts_from_alerts(with_priors),
        route_counts=_counts_from_decisions(routed.decisions),
        score_before_after=tuple(prior_scores[:50]),
        tier_changes=tuple(tier_changes[:50]),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def load_raw_events_jsonl(path: str | Path) -> list[RawDiscoveredEvent]:
    rows = load_jsonl_rows(path)
    out: list[RawDiscoveredEvent] = []
    for row in rows:
        raw = _raw_event_from_row(row)
        if raw is not None:
            out.append(raw)
    return out


def load_market_rows(path: str | Path | None) -> list[dict[str, Any]]:
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return [dict(row) for row in raw if isinstance(row, Mapping)]
    if isinstance(raw, Mapping):
        for key in ("coins", "markets", "rows", "data"):
            rows = raw.get(key)
            if isinstance(rows, list):
                return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def assets_from_market_rows(rows: Iterable[Mapping[str, Any]]) -> list[DiscoveredAsset]:
    return assets_from_markets([dict(row) for row in rows if isinstance(row, Mapping)])


def load_jsonl_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path).expanduser()
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def format_replay_report(result: EventAlphaReplayResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA REPLAY REPORT (local artifacts only)",
        "=" * 76,
        f"alerts={result.alert_rows} · watchlist_rows={result.watchlist_rows}",
        f"raw_events={result.raw_events} · candidates={result.candidates} · alertable={result.alertable_count}",
        f"priors_enabled={str(result.priors_enabled).lower()} · llm_advisory={str(result.llm_advisory).lower()}",
        "tiers: " + _fmt_counts(result.tier_counts or {}),
        "tiers_with_priors: " + _fmt_counts(result.tier_counts_with_priors or {}),
        "routes: " + _fmt_counts(result.route_counts or {}),
    ]
    if result.score_before_after:
        lines.append("")
        lines.append("Prior score comparison:")
        for key, before, after in result.score_before_after[:20]:
            lines.append(f"- {key or 'unknown'}: {before} -> {after}")
    if result.tier_changes:
        lines.append("")
        lines.append("Tier changes:")
        for key, before, after in result.tier_changes[:20]:
            lines.append(f"- {key or 'unknown'}: {before} -> {after}")
    if result.warnings:
        lines.append("")
        lines.append("warnings: " + "; ".join(result.warnings))
    lines.append("No live providers, Telegram sends, paper trades, live DB rows, or execution were used.")
    return "\n".join(lines)


def _counts(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "unknown")
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def _fmt_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _raw_event_from_row(row: Mapping[str, Any]) -> RawDiscoveredEvent | None:
    raw_id = str(row.get("raw_id") or row.get("id") or "").strip()
    title = str(row.get("title") or row.get("event_name") or "").strip()
    if not raw_id or not title:
        return None
    raw_json = row.get("raw_json")
    if not isinstance(raw_json, dict):
        raw_json = {key: value for key, value in row.items() if key not in {"schema_version", "row_type"}}
    fetched = parse_datetime(row.get("fetched_at")) or parse_datetime(row.get("observed_at")) or datetime.now(timezone.utc)
    published = parse_datetime(row.get("published_at"))
    return RawDiscoveredEvent(
        raw_id=raw_id,
        provider=str(row.get("provider") or row.get("source") or "replay"),
        fetched_at=fetched,
        published_at=published,
        source_url=str(row.get("source_url") or "") or None,
        title=title,
        body=str(row.get("body") or row.get("description") or "") or None,
        raw_json=dict(raw_json),
        source_confidence=_float(row.get("source_confidence"), 0.75),
        content_hash=str(row.get("content_hash") or raw_id),
    )


def _counts_from_alerts(alerts: Iterable[event_alerts.EventAlertCandidate]) -> dict[str, int]:
    out: dict[str, int] = {}
    for alert in alerts:
        out[alert.tier.value] = out.get(alert.tier.value, 0) + 1
    return dict(sorted(out.items()))


def _counts_from_decisions(decisions: Iterable[event_alpha_router.EventAlphaRouteDecision]) -> dict[str, int]:
    out: dict[str, int] = {}
    for decision in decisions:
        out[decision.route.value] = out.get(decision.route.value, 0) + 1
    return dict(sorted(out.items()))


def _alert_key(alert: event_alerts.EventAlertCandidate) -> str:
    event = alert.discovery_candidate.event
    return "|".join((
        str(event.event_id or ""),
        str(alert.coin_id or ""),
        str(alert.effective_playbook_type or alert.playbook_type or ""),
    ))


def _float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
