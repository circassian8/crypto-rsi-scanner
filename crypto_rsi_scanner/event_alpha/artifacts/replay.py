"""Local-artifact replay summaries for Event Alpha Radar research runs."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.artifacts.alerts as event_alerts
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
import crypto_rsi_scanner.event_alpha.radar.llm.analyzer as event_llm_analyzer
import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist
from ...event_alpha.outcomes import priors as event_alpha_priors
from crypto_rsi_scanner.event_core.models import DiscoveredAsset, RawDiscoveredEvent
from ...event_providers.coingecko_universe import assets_from_markets
from ...event_providers.manual_json import parse_datetime


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
    candidate_rows: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventAlphaReplayPolicyRow:
    policy: str
    alerts: int
    alertable: int
    tier_counts: dict[str, int]
    route_counts: dict[str, int]
    score_deltas: tuple[tuple[str, int, int], ...] = ()
    tier_changes: tuple[tuple[str, str, str], ...] = ()
    candidate_rows: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class EventAlphaReplayCandidateDiff:
    policy: str
    alert_key: str
    symbol: str
    playbook: str
    baseline_score: int | None
    variant_score: int | None
    baseline_tier: str | None
    variant_tier: str | None
    baseline_route: str | None
    variant_route: str | None
    score_delta: int | None
    tier_changed: bool
    route_changed: bool
    feedback_label: str | None = None
    primary_return: float | None = None


@dataclass(frozen=True)
class EventAlphaReplayComparisonResult:
    rows: tuple[EventAlphaReplayPolicyRow, ...]
    diffs: tuple[EventAlphaReplayCandidateDiff, ...] = ()
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
        candidate_rows=tuple(_candidate_row_from_mapping(row) for row in alerts),
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
    with_priors = event_alpha_priors.apply_priors_shadow(
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
    route_by_key = {
        decision.entry.key: decision.route.value
        for decision in routed.decisions
    }
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
        candidate_rows=tuple(
            _candidate_row_from_alert(alert, route_by_key.get(event_watchlist.watchlist_key(alert)))
            for alert in with_priors
        ),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def compare_replay_policies(
    *,
    raw_events: Iterable[RawDiscoveredEvent],
    assets: Iterable[DiscoveredAsset],
    market_rows: Iterable[Mapping[str, Any]] = (),
    policies: Iterable[str] = ("baseline", "llm_advisory", "priors"),
    alert_cfg: event_alerts.EventAlertConfig | None = None,
    priors_cfg: event_alpha_priors.EventAlphaPriorsConfig | None = None,
    llm_provider: object | None = None,
    llm_cfg: event_llm_analyzer.EventLLMConfig | None = None,
    router_cfg: event_alpha_router.EventAlphaRouterConfig | None = None,
    router_threshold_variant: event_alpha_router.EventAlphaRouterConfig | None = None,
    profile_variant_router_cfg: event_alpha_router.EventAlphaRouterConfig | None = None,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    outcome_rows: Iterable[Mapping[str, Any]] = (),
    now: datetime | None = None,
) -> EventAlphaReplayComparisonResult:
    """Compare named local replay policies without provider calls or sends."""
    raw = tuple(raw_events)
    asset_rows = tuple(assets)
    market = tuple(dict(row) for row in market_rows if isinstance(row, Mapping))
    supplied_feedback = tuple(
        dict(row) for row in feedback_rows if isinstance(row, Mapping)
    )
    supplied_outcomes = tuple(
        dict(row) for row in outcome_rows if isinstance(row, Mapping)
    )
    base_router = router_cfg or event_alpha_router.EventAlphaRouterConfig(enabled=True)
    priors_enabled_cfg = event_alpha_priors.EventAlphaPriorsConfig(
        enabled=True,
        path=priors_cfg.path if priors_cfg else None,
        min_multiplier=priors_cfg.min_multiplier if priors_cfg else 0.70,
        max_multiplier=priors_cfg.max_multiplier if priors_cfg else 1.30,
    )
    rows: list[EventAlphaReplayPolicyRow] = []
    warnings: list[str] = ["policy comparison is local-only; no live providers or sends were attempted"]
    if supplied_feedback or supplied_outcomes:
        warnings.append(
            "historical feedback/outcome annotations were omitted because replay "
            "candidates do not carry an exact canonical Core identity"
        )
    for policy in [str(item).strip().lower() for item in policies if str(item).strip()]:
        use_llm = policy in {"llm", "llm_advisory"}
        use_priors = policy == "priors"
        active_router = base_router
        if policy == "router_threshold_variant":
            active_router = router_threshold_variant or event_alpha_router.EventAlphaRouterConfig(
                enabled=base_router.enabled,
                include_suppressed=base_router.include_suppressed,
                daily_digest_enabled=base_router.daily_digest_enabled,
                instant_enabled=base_router.instant_enabled,
                max_digest_items=base_router.max_digest_items,
                max_high_priority_per_day=base_router.max_high_priority_per_day,
                per_key_cooldown_hours=base_router.per_key_cooldown_hours,
                alert_on_score_jump=True,
                score_jump_threshold=max(1, base_router.score_jump_threshold // 2),
                alert_on_new_independent_source=base_router.alert_on_new_independent_source,
                alert_on_event_time_upgrade=base_router.alert_on_event_time_upgrade,
                alert_on_derivatives_crowding_upgrade=base_router.alert_on_derivatives_crowding_upgrade,
                alert_on_cluster_confidence_upgrade=base_router.alert_on_cluster_confidence_upgrade,
            )
        elif policy == "profile_variant":
            active_router = profile_variant_router_cfg or base_router
        replay = replay_from_raw_events(
            raw_events=raw,
            assets=asset_rows,
            market_rows=market,
            alert_cfg=alert_cfg,
            priors_cfg=priors_enabled_cfg if use_priors else event_alpha_priors.EventAlphaPriorsConfig(enabled=False),
            llm_provider=llm_provider if use_llm else None,
            llm_cfg=llm_cfg if use_llm else None,
            router_cfg=active_router,
            now=now,
        )
        rows.append(EventAlphaReplayPolicyRow(
            policy=policy,
            alerts=replay.alert_rows,
            alertable=replay.alertable_count,
            tier_counts=replay.tier_counts_with_priors or replay.tier_counts or {},
            route_counts=replay.route_counts or {},
            score_deltas=replay.score_before_after,
            tier_changes=replay.tier_changes,
            candidate_rows=replay.candidate_rows,
        ))
        warnings.extend(replay.warnings)
    diffs = _policy_diffs(
        rows,
        feedback_rows=(),
        outcome_rows=(),
        baseline_policy=str(rows[0].policy) if rows else "baseline",
    )
    return EventAlphaReplayComparisonResult(
        rows=tuple(rows),
        diffs=diffs,
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


def format_replay_comparison_report(result: EventAlphaReplayComparisonResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA REPLAY POLICY COMPARISON (local artifacts only)",
        "=" * 76,
    ]
    if not result.rows:
        lines.append("No replay policy rows.")
        return "\n".join(lines)
    baseline = result.rows[0]
    baseline_routes = baseline.route_counts
    for row in result.rows:
        lines.append(
            f"{row.policy}: alerts={row.alerts} alertable={row.alertable} "
            f"alertable_delta={row.alertable - baseline.alertable:+d}"
        )
        lines.append("  tiers: " + _fmt_counts(row.tier_counts))
        lines.append("  routes: " + _fmt_counts(row.route_counts))
        route_changes = _count_delta(row.route_counts, baseline_routes)
        if route_changes:
            lines.append("  route_delta: " + _fmt_counts(route_changes))
        if row.score_deltas:
            lines.append(
                "  score_deltas: "
                + "; ".join(f"{key or 'unknown'} {before}->{after}" for key, before, after in row.score_deltas[:8])
            )
        if row.tier_changes:
            lines.append(
                "  tier_changes: "
                + "; ".join(f"{key or 'unknown'} {before}->{after}" for key, before, after in row.tier_changes[:8])
            )
    if result.diffs:
        gained = sum(1 for diff in result.diffs if diff.baseline_tier is None and diff.variant_tier is not None)
        lost = sum(1 for diff in result.diffs if diff.baseline_tier is not None and diff.variant_tier is None)
        route_changed = sum(1 for diff in result.diffs if diff.route_changed)
        tier_up = sum(1 for diff in result.diffs if _tier_rank(diff.variant_tier) > _tier_rank(diff.baseline_tier))
        tier_down = sum(1 for diff in result.diffs if _tier_rank(diff.variant_tier) < _tier_rank(diff.baseline_tier))
        lines.extend([
            "",
            "candidate diffs:",
            (
                f"summary: gained={gained} lost={lost} tier_upgrades={tier_up} "
                f"tier_downgrades={tier_down} route_changes={route_changed}"
            ),
        ])
        for diff in sorted(result.diffs, key=lambda item: abs(item.score_delta or 0), reverse=True)[:20]:
            lines.append(
                f"- {diff.policy} {diff.symbol or 'UNKNOWN'} {diff.alert_key}: "
                f"score={_fmt_optional(diff.baseline_score)}->{_fmt_optional(diff.variant_score)} "
                f"tier={diff.baseline_tier or 'none'}->{diff.variant_tier or 'none'} "
                f"route={diff.baseline_route or 'none'}->{diff.variant_route or 'none'} "
                f"feedback={diff.feedback_label or 'none'} primary_return={_fmt_return(diff.primary_return)}"
            )
    if result.warnings:
        lines.append("")
        lines.append("warnings: " + "; ".join(result.warnings))
    lines.append("No live providers, Telegram sends, paper trades, live DB rows, or execution were used.")
    return "\n".join(lines).rstrip()


def _count_delta(current: Mapping[str, int], baseline: Mapping[str, int]) -> dict[str, int]:
    keys = set(current) | set(baseline)
    return {key: int(current.get(key, 0)) - int(baseline.get(key, 0)) for key in sorted(keys) if int(current.get(key, 0)) != int(baseline.get(key, 0))}


def _policy_diffs(
    rows: Iterable[EventAlphaReplayPolicyRow],
    *,
    feedback_rows: Iterable[Mapping[str, Any]],
    outcome_rows: Iterable[Mapping[str, Any]],
    baseline_policy: str,
) -> tuple[EventAlphaReplayCandidateDiff, ...]:
    policy_rows = list(rows)
    baseline = next((row for row in policy_rows if row.policy == baseline_policy), policy_rows[0] if policy_rows else None)
    if baseline is None:
        return ()
    baseline_by_key = {str(row.get("alert_key") or ""): row for row in baseline.candidate_rows}
    feedback = _feedback_by_key(feedback_rows)
    outcomes = _outcome_by_key(outcome_rows)
    diffs: list[EventAlphaReplayCandidateDiff] = []
    for row in policy_rows:
        if row.policy == baseline.policy:
            continue
        variant_by_key = {str(item.get("alert_key") or ""): item for item in row.candidate_rows}
        for key in sorted(set(baseline_by_key) | set(variant_by_key)):
            base = baseline_by_key.get(key)
            variant = variant_by_key.get(key)
            base_score = _optional_int(base.get("score") if base else None)
            variant_score = _optional_int(variant.get("score") if variant else None)
            score_delta = None if base_score is None or variant_score is None else variant_score - base_score
            base_tier = _optional_str(base.get("tier") if base else None)
            variant_tier = _optional_str(variant.get("tier") if variant else None)
            base_route = _optional_str(base.get("route") if base else None)
            variant_route = _optional_str(variant.get("route") if variant else None)
            if (
                score_delta == 0
                and base_tier == variant_tier
                and base_route == variant_route
                and base is not None
                and variant is not None
            ):
                continue
            sample = variant or base or {}
            watch_key = str(sample.get("watchlist_key") or "")
            outcome = outcomes.get(key) or outcomes.get(watch_key)
            diffs.append(EventAlphaReplayCandidateDiff(
                policy=row.policy,
                alert_key=key,
                symbol=str(sample.get("symbol") or ""),
                playbook=str(sample.get("playbook") or ""),
                baseline_score=base_score,
                variant_score=variant_score,
                baseline_tier=base_tier,
                variant_tier=variant_tier,
                baseline_route=base_route,
                variant_route=variant_route,
                score_delta=score_delta,
                tier_changed=base_tier != variant_tier,
                route_changed=base_route != variant_route,
                feedback_label=feedback.get(key) or feedback.get(watch_key),
                primary_return=_optional_float(outcome.get("primary_horizon_return")) if outcome else None,
            ))
    return tuple(diffs)


def _feedback_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Index only prevalidated exact-Core projections; replay currently has no bridge."""

    out: dict[str, str] = {}
    ambiguous: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        label = str(row.get("feedback_label") or "").strip()
        core_id = str(row.get("core_opportunity_id") or "").strip()
        if row.get("calibration_eligible") is not True or not label or not core_id:
            continue
        if core_id in out:
            ambiguous.add(core_id)
            out.pop(core_id, None)
            continue
        if core_id not in ambiguous:
            out[core_id] = label
    return out


def _outcome_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index only unique exact-Core observed outcomes; never legacy aliases."""

    out: dict[str, dict[str, Any]] = {}
    ambiguous: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        core_id = str(row.get("core_opportunity_id") or "").strip()
        if (
            row.get("calibration_eligible") is not True
            or row.get("outcome_data_source") != "observed_market_prices"
            or not core_id
        ):
            continue
        if core_id in out:
            ambiguous.add(core_id)
            out.pop(core_id, None)
            continue
        if core_id not in ambiguous:
            out[core_id] = dict(row)
    return out


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


def _candidate_row_from_alert(alert: event_alerts.EventAlertCandidate, route: str | None) -> dict[str, Any]:
    watch_key = event_watchlist.watchlist_key(alert)
    return {
        "alert_key": _alert_key(alert),
        "watchlist_key": watch_key,
        "symbol": alert.symbol,
        "coin_id": alert.coin_id,
        "playbook": alert.effective_playbook_type or alert.playbook_type or "",
        "score": alert.opportunity_score,
        "tier": alert.tier.value,
        "route": route or "STORE_ONLY",
    }


def _candidate_row_from_mapping(row: Mapping[str, Any]) -> dict[str, Any]:
    alert_key = str(row.get("alert_key") or row.get("snapshot_id") or row.get("event_id") or "")
    return {
        "alert_key": alert_key,
        "watchlist_key": str(row.get("watchlist_key") or row.get("alert_key") or ""),
        "symbol": str(row.get("asset_symbol") or row.get("symbol") or ""),
        "coin_id": str(row.get("asset_coin_id") or row.get("coin_id") or ""),
        "playbook": str(row.get("effective_playbook_type") or row.get("playbook_type") or ""),
        "score": _int(row.get("opportunity_score") or row.get("latest_score")),
        "tier": str(row.get("tier") or row.get("latest_tier") or ""),
        "route": str(row.get("route") or "STORE_ONLY"),
    }


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


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _tier_rank(value: str | None) -> int:
    order = {
        None: -1,
        "": -1,
        "STORE_ONLY": 0,
        "RADAR_DIGEST": 1,
        "WATCHLIST": 2,
        "HIGH_PRIORITY_WATCH": 3,
        "TRIGGERED_FADE": 4,
    }
    return order.get(value, 0)


def _fmt_optional(value: object) -> str:
    return "none" if value is None else str(value)


def _fmt_return(value: float | None) -> str:
    return "none" if value is None else f"{value:.4f}"


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
