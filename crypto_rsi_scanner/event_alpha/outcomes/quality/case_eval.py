"""Split implementation for `crypto_rsi_scanner/event_alpha/outcomes/quality.py` (case_eval)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping
from .... import (
    event_alpha_alert_store,
    event_alpha_quality_fields,
    event_alpha_router,
    event_watchlist,
)
from ...artifacts import reason_text as event_alpha_reason_text
from ...artifacts import context as event_alpha_artifacts
from ...radar import core_opportunities as event_core_opportunities
from ...radar import opportunity_verdict as event_opportunity_verdict
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .... import event_alpha_quality_fields
from ...artifacts import run_ledger as event_alpha_run_ledger
from datetime import datetime, timezone
from types import SimpleNamespace
from .... import (
    event_claim_semantics,
    event_evidence_quality,
    event_incident_graph,
    event_impact_path_validator,
    event_market_confirmation,
)
from crypto_rsi_scanner.event_core.models import NormalizedEvent, RawDiscoveredEvent
from ...radar import incidents as event_incident_store
from .models import *  # noqa: F403

def load_signal_quality_cases(path: str | Path = DEFAULT_SIGNAL_QUALITY_CASES_PATH) -> tuple[dict[str, Any], ...]:
    p = Path(path).expanduser()
    data = json.loads(p.read_text(encoding="utf-8"))
    cases = data.get("cases") if isinstance(data, Mapping) else data
    if not isinstance(cases, list):
        raise ValueError("signal quality fixture must contain a list or {'cases': [...]}")
    return tuple(dict(case) for case in cases if isinstance(case, Mapping))
def evaluate_signal_quality_cases(
    path: str | Path = DEFAULT_SIGNAL_QUALITY_CASES_PATH,
) -> SignalQualityEvalResult:
    p = Path(path).expanduser()
    results = tuple(evaluate_signal_quality_case(case) for case in load_signal_quality_cases(p))
    passed = sum(1 for result in results if result.passed)
    return SignalQualityEvalResult(
        path=p,
        total_cases=len(results),
        passed_cases=passed,
        failed_cases=len(results) - passed,
        case_results=results,
    )
def evaluate_signal_quality_case(case: Mapping[str, Any]) -> SignalQualityCaseResult:
    case_id = str(case.get("case_id") or "unknown")
    title = str(case.get("title") or case_id)
    raw = _raw_event(case)
    hypothesis = _hypothesis(case)
    symbol = _optional_str(case.get("candidate_symbol"))
    coin_id = _optional_str(case.get("candidate_coin_id"))
    identity_rejection = _identity_rejection_reason(raw, symbol=symbol, coin_id=coin_id)

    impact = event_impact_path_validator.validate_impact_path(
        raw,
        hypothesis,
        symbol=symbol,
        coin_id=coin_id,
        score_components=dict(case.get("score_components") or {}),
    )
    claims = event_claim_semantics.extract_event_claims((raw,))
    archetype = event_incident_graph.event_archetype(None, (raw,), claims=claims)
    incident = event_incident_graph.build_incidents(
        (_normalized_event_for_case(case, raw),),
        {raw.raw_id: raw},
    )[0]
    market = _market_confirmation_for_case(case, raw)
    evidence = event_evidence_quality.evaluate_evidence_quality(
        raw,
        hypothesis=hypothesis,
        symbol=symbol,
        coin_id=coin_id,
    )
    components = _score_components_for_case(
        case,
        market=market,
        evidence=evidence,
        identity_rejection=identity_rejection,
        symbol=symbol,
    )
    verdict = event_opportunity_verdict.evaluate_opportunity(
        impact_path=impact,
        market_confirmation=market,
        evidence_quality=evidence,
        hypothesis=hypothesis,
        score_components=components,
    )
    (
        opportunity_level,
        route_tier,
        digest,
        watchlist,
        high_priority,
        blocked,
        reason_codes,
    ) = _routing_outcome_for_case(
        verdict,
        evidence=evidence,
        market=market,
        impact=impact,
        identity_rejection=identity_rejection,
    )
    incident_hypothesis_generated = bool(
        case.get(
            "incident_hypothesis_generated",
            bool(case.get("candidate_symbol") or case.get("candidate_coin_id")),
        )
    )
    incident_hypothesis_row = _incident_hypothesis_row(
        hypothesis,
        incident_id=incident.incident_id,
        symbol=symbol,
        coin_id=coin_id,
        impact=impact,
        evidence=evidence,
        verdict=verdict,
        opportunity_level=opportunity_level,
        identity_rejection=identity_rejection,
    )
    incident_relevance = event_incident_store.classify_incident_relevance(
        incident,
        raw_by_id={raw.raw_id: raw},
        hypotheses=(incident_hypothesis_row,) if incident_hypothesis_generated else (),
        watchlist_rows=(),
    )
    core_opportunities = event_core_opportunities.aggregate_core_opportunities((incident_hypothesis_row,))
    core = core_opportunities[0] if core_opportunities else None
    reported_impact_path = impact.impact_path_type
    reported_role = impact.candidate_role
    if not symbol and not coin_id:
        reported_impact_path = "generic_cooccurrence_only"
        reported_role = "generic_mention"
        reason_codes = tuple(dict.fromkeys((*reason_codes, "needs_identity_validation", "candidate_discovery_pending")))
    false_positive_reason = _false_positive_reason(
        identity_rejection=identity_rejection,
        impact_path_type=reported_impact_path,
        candidate_role=reported_role,
        incident_relevance_status=incident_relevance["incident_relevance_status"],
        source_class=evidence.source_class,
    )
    brief_section = _brief_section(
        opportunity_level=opportunity_level,
        route_tier=route_tier,
        identity_rejection=identity_rejection,
        false_positive_reason=false_positive_reason,
    )
    actual = _actual_signal_quality_case(
        raw=raw,
        claims=claims,
        archetype=archetype,
        impact=impact,
        market=market,
        evidence=evidence,
        incident=incident,
        incident_relevance=incident_relevance,
        core=core,
        reported_impact_path=reported_impact_path,
        reported_role=reported_role,
        opportunity_level=opportunity_level,
        route_tier=route_tier,
        digest=digest,
        watchlist=watchlist,
        high_priority=high_priority,
        reason_codes=reason_codes,
        blocked=blocked,
        identity_rejection=identity_rejection,
        false_positive_reason=false_positive_reason,
        brief_section=brief_section,
    )
    expected = _expected(case)
    diffs, stages = _diff_expected(expected, actual)
    return SignalQualityCaseResult(
        case_id=case_id,
        title=title,
        passed=not diffs,
        stage_failures=tuple(stages),
        expected=expected,
        actual=actual,
        diffs=tuple(diffs),
    )


def _market_confirmation_for_case(
    case: Mapping[str, Any],
    raw: RawDiscoveredEvent,
) -> event_market_confirmation.EventMarketConfirmationResult:
    observed_at = (
        case.get("market_context_observed_at")
        if "market_context_observed_at" in case
        else raw.fetched_at.isoformat()
    )
    return event_market_confirmation.evaluate_market_confirmation(
        event_market_confirmation.EventMarketConfirmationInput(
            market_snapshot=_mapping(case.get("market_snapshot")),
            derivatives_snapshot=_mapping(case.get("derivatives_snapshot")),
            supply_snapshot=_mapping(case.get("supply_snapshot")),
            btc_context=_mapping(case.get("btc_context")),
            sector_benchmark=_mapping(case.get("sector_benchmark")),
            playbook_type=str(case.get("playbook_hint") or case.get("impact_category") or ""),
            impact_category=str(case.get("impact_category") or ""),
            now=case.get("now") or "2026-06-15T16:00:00Z",
            market_context_observed_at=observed_at,
            market_context_source=str(case.get("market_context_source") or "fixture_signal_quality"),
            market_context_max_age_hours=float(case.get("market_context_max_age_hours") or 6.0),
            allow_stale_fixture_market_context=bool(case.get("allow_stale_fixture_market_context", True)),
            stale_cap_level=str(case.get("stale_cap_level") or "weak"),
        )
    )


def _score_components_for_case(
    case: Mapping[str, Any],
    *,
    market: event_market_confirmation.EventMarketConfirmationResult,
    evidence: event_evidence_quality.EvidenceQualityResult,
    identity_rejection: str | None,
    symbol: str | None,
) -> dict[str, Any]:
    components = dict(case.get("score_components") or {})
    components.update({
        "market_confirmation": market.market_confirmation_score,
        "source_quality": evidence.evidence_quality_score,
        "source_class": evidence.source_class,
        "evidence_specificity": evidence.evidence_specificity,
        "validation_strength": 95.0 if not identity_rejection and symbol else 30.0,
        "candidate_asset_strength": 90.0 if not identity_rejection and symbol else 10.0,
        "timing_event_window": float(case.get("timing_event_window") or components.get("event_clarity") or 70.0),
        "liquidity_tradability": max(float(case.get("liquidity_tradability") or 0.0), market.market_confirmation_score),
    })
    return components


def _routing_outcome_for_case(
    verdict: event_opportunity_verdict.OpportunityVerdict,
    *,
    evidence: event_evidence_quality.EvidenceQualityResult,
    market: event_market_confirmation.EventMarketConfirmationResult,
    impact: event_impact_path_validator.ImpactPathValidation,
    identity_rejection: str | None,
) -> tuple[str, str, bool, bool, bool, str | None, tuple[str, ...]]:
    opportunity_level = verdict.opportunity_level
    route_tier = _route_tier(opportunity_level)
    digest = verdict.digest_eligible
    watchlist = verdict.watchlist_eligible
    high_priority = verdict.high_priority_eligible
    reason_codes = tuple(dict.fromkeys((
        *(verdict.verdict_reason_codes or ()),
        *(verdict.missing_requirements or ()),
        *(evidence.reason_codes or ()),
        *(market.reasons or ()),
        *(market.warnings or ()),
        impact.impact_path_reason,
    )))
    blocked = verdict.why_local_only or verdict.why_not_watchlist
    if identity_rejection:
        opportunity_level = "local_only"
        route_tier = "STORE_ONLY"
        digest = False
        watchlist = False
        high_priority = False
        blocked = identity_rejection
        reason_codes = tuple(dict.fromkeys((*reason_codes, identity_rejection, "needs_identity_validation")))
    return opportunity_level, route_tier, digest, watchlist, high_priority, blocked, reason_codes


def _actual_signal_quality_case(
    *,
    raw: RawDiscoveredEvent,
    claims: Iterable[Any],
    archetype: str,
    impact: event_impact_path_validator.ImpactPathValidation,
    market: event_market_confirmation.EventMarketConfirmationResult,
    evidence: event_evidence_quality.EvidenceQualityResult,
    incident: Any,
    incident_relevance: Mapping[str, Any],
    core: Any,
    reported_impact_path: str,
    reported_role: str,
    opportunity_level: str,
    route_tier: str,
    digest: bool,
    watchlist: bool,
    high_priority: bool,
    reason_codes: tuple[str, ...],
    blocked: str | None,
    identity_rejection: str | None,
    false_positive_reason: str,
    brief_section: str,
) -> dict[str, Any]:
    catalyst_frame = (raw.raw_json if isinstance(raw.raw_json, Mapping) else {}).get(
        "llm_catalyst_frame_validation",
        {},
    )
    return {
        "impact_path_type": reported_impact_path,
        "candidate_role": reported_role,
        "claim_polarities": tuple(dict.fromkeys(claim.polarity for claim in claims)),
        "cause_status": event_claim_semantics.current_cause_status(claims, "exploit"),
        "event_archetype": archetype,
        "primary_subject": impact.primary_subject,
        "affected_ecosystem": impact.affected_ecosystem,
        "market_reaction_confirmed": market.level in {"weak", "moderate", "strong"},
        "causal_mechanism_confirmed": _causal_mechanism_confirmed(impact),
        "evidence_specificity": evidence.evidence_specificity,
        "market_confirmation_level": market.level,
        "market_context_freshness_status": market.market_context_freshness_status,
        "market_context_age_hours": market.market_context_age_hours,
        "freshness_cap_applied": market.freshness_cap_applied,
        "opportunity_level": opportunity_level,
        "route_tier": route_tier,
        "digest_eligible": digest,
        "watchlist_eligible": watchlist,
        "high_priority_eligible": high_priority,
        "reason_codes": reason_codes,
        "blocked_reason": blocked,
        "triggered_fade": False,
        "identity_rejection_reason": identity_rejection,
        "incident_relevance_status": incident_relevance["incident_relevance_status"],
        "incident_relevance_score": incident_relevance["incident_relevance_score"],
        "canonical_persistence_reason": incident_relevance["canonical_persistence_reason"],
        "qualified_link_count": incident_relevance.get("qualified_link_count"),
        "weak_link_count": incident_relevance.get("weak_link_count"),
        "quality_blocked_link_count": incident_relevance.get("quality_blocked_link_count"),
        "unknown_role_link_count": incident_relevance.get("unknown_role_link_count"),
        "link_quality_reasons": incident_relevance.get("link_quality_reasons"),
        "diagnostic_hidden_by_default": _incident_hidden_by_default(incident_relevance),
        "external_context_hidden_by_default": incident_relevance["incident_relevance_status"]
        == event_incident_store.RELEVANCE_EXTERNAL_CONTEXT_ONLY,
        "selected_main_frame_type": incident.main_frame_type,
        "background_frame_count": _frame_role_count(incident.frame_summary, {"background_context", "historical_context"}),
        "negated_frame_count": _frame_role_count(incident.frame_summary, {"negated_claim", "corrective_context"}),
        "frame_rule_disagreement": bool(catalyst_frame.get("frame_rule_disagreement", False)),
        "frame_disagreement_resolution": catalyst_frame.get("resolution"),
        "core_opportunity_id": core.core_opportunity_id if core is not None else None,
        "aggregation_status": "core_opportunity" if core is not None else "no_validated_core",
        "near_miss_inclusion": _near_miss_status(opportunity_level, route_tier, identity_rejection),
        "card_group": _card_group(opportunity_level, route_tier, identity_rejection),
        "brief_section": brief_section,
        "diagnostic_visibility": _diagnostic_visibility(brief_section),
        "false_positive_reason": false_positive_reason,
        "human_readable_reason": _human_readable_reason(blocked, identity_rejection, reason_codes),
        "frame_counter_status": "frame_present" if incident.main_frame_type else "frame_not_required_or_missing",
    }


def _causal_mechanism_confirmed(impact: event_impact_path_validator.ImpactPathValidation) -> bool:
    return impact.cause_status == "confirmed" or (
        impact.impact_path_strength in {"strong", "medium"}
        and impact.impact_path_type != "market_dislocation_unknown"
        and impact.impact_path_reason not in {"alleged_exploit_unconfirmed", "cause_unknown_market_dislocation"}
    )


def _incident_hidden_by_default(incident_relevance: Mapping[str, Any]) -> bool:
    return incident_relevance["incident_relevance_status"] in {
        event_incident_store.RELEVANCE_RAW_OBSERVATION,
        event_incident_store.RELEVANCE_EXTERNAL_CONTEXT_ONLY,
        event_incident_store.RELEVANCE_DIAGNOSTIC_ONLY,
        event_incident_store.RELEVANCE_REJECTED_INCIDENT,
    }
def format_signal_quality_eval(result: SignalQualityEvalResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA SIGNAL QUALITY EVAL (offline fixtures; research-only)",
        "=" * 76,
        f"path: {result.path}",
        f"cases: {result.total_cases} · passed: {result.passed_cases} · failed: {result.failed_cases}",
    ]
    failures_by_stage: dict[str, int] = {}
    for case in result.case_results:
        for stage in case.stage_failures:
            failures_by_stage[stage] = failures_by_stage.get(stage, 0) + 1
    lines.append(
        "failures_by_stage: "
        + (", ".join(f"{stage}={count}" for stage, count in sorted(failures_by_stage.items())) or "none")
    )
    for case in result.case_results:
        status = "PASS" if case.passed else "FAIL"
        lines.append("")
        lines.append(f"{status} {case.case_id}: {case.title}")
        if case.passed:
            lines.append(
                "  actual: "
                f"path={case.actual.get('impact_path_type')} role={case.actual.get('candidate_role')} "
                f"market={case.actual.get('market_confirmation_level')} "
                f"freshness={case.actual.get('market_context_freshness_status')} "
                f"age_h={case.actual.get('market_context_age_hours')} "
                f"cap={case.actual.get('freshness_cap_applied')} "
                f"level={case.actual.get('opportunity_level')} route={case.actual.get('route_tier')} "
                f"core={case.actual.get('core_opportunity_id') or 'none'} "
                f"aggregation={case.actual.get('aggregation_status')} "
                f"near_miss={case.actual.get('near_miss_inclusion')} "
                f"card_group={case.actual.get('card_group')} "
                f"brief_section={case.actual.get('brief_section')} "
                f"diagnostic_visibility={case.actual.get('diagnostic_visibility')} "
                f"false_positive={case.actual.get('false_positive_reason')} "
                f"reason=\"{case.actual.get('human_readable_reason')}\" "
                f"frame_counter={case.actual.get('frame_counter_status')}"
            )
            continue
        for diff in case.diffs:
            lines.append(f"  diff: {diff}")
        lines.append("  expected: " + _compact(case.expected))
        lines.append("  actual: " + _compact(case.actual))
    lines.append("")
    lines.append("No live providers, Telegram sends, paper trades, normal RSI rows, or execution were used.")
    return "\n".join(lines).rstrip()
def _raw_event(case: Mapping[str, Any]) -> RawDiscoveredEvent:
    row = dict(case.get("raw_event") or {})
    fetched_at = _parse_dt(row.get("fetched_at")) or datetime(2026, 6, 15, tzinfo=timezone.utc)
    published_at = _parse_dt(row.get("published_at"))
    raw_json = dict(row.get("raw_json") or {})
    raw_json.setdefault("market", dict(case.get("market_snapshot") or {}))
    raw_json.setdefault("derivatives", dict(case.get("derivatives_snapshot") or {}))
    raw_json.setdefault("supply", dict(case.get("supply_snapshot") or {}))
    return RawDiscoveredEvent(
        raw_id=str(row.get("raw_id") or case.get("case_id") or "signal-quality-case"),
        provider=str(row.get("provider") or "fixture_signal_quality"),
        fetched_at=fetched_at,
        published_at=published_at,
        source_url=_optional_str(row.get("source_url")),
        title=str(row.get("title") or case.get("title") or ""),
        body=_optional_str(row.get("body")),
        raw_json=raw_json,
        source_confidence=float(row.get("source_confidence") or case.get("source_confidence") or 0.8),
        content_hash=str(row.get("content_hash") or row.get("raw_id") or case.get("case_id") or ""),
    )
def _frame_role_count(frame_summary: Iterable[Mapping[str, Any]], roles: set[str]) -> int:
    keys = {
        (
            str(frame.get("frame_type") or ""),
            str(frame.get("subject") or ""),
        )
        for frame in frame_summary
        if isinstance(frame, Mapping) and str(frame.get("frame_role") or "") in roles
    }
    return len(keys)
def _normalized_event_for_case(case: Mapping[str, Any], raw: RawDiscoveredEvent) -> NormalizedEvent:
    return NormalizedEvent(
        event_id=str(case.get("event_id") or case.get("case_id") or raw.raw_id),
        raw_ids=(raw.raw_id,),
        event_name=str(case.get("title") or raw.title or raw.raw_id),
        event_type=str(case.get("event_type") or case.get("impact_category") or "news"),
        event_time=None,
        event_time_confidence=0.0,
        first_seen_time=raw.fetched_at,
        source=str(raw.provider or "fixture_signal_quality"),
        source_urls=(raw.source_url,) if raw.source_url else (),
        external_asset=_optional_str(case.get("external_asset")),
        description=raw.body,
        confidence=float(case.get("source_confidence") or raw.source_confidence or 0.8),
    )
def _hypothesis(case: Mapping[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        impact_category=str(case.get("impact_category") or "market_anomaly_unknown"),
        external_asset=_optional_str(case.get("external_asset")),
        playbook_hint=_optional_str(case.get("playbook_hint")) or _optional_str(case.get("impact_category")),
        score_components=dict(case.get("score_components") or {}),
    )
def _incident_hypothesis_row(
    hypothesis: SimpleNamespace,
    *,
    incident_id: str,
    symbol: str | None,
    coin_id: str | None,
    impact: event_impact_path_validator.ImpactPathValidation,
    evidence: event_evidence_quality.EvidenceQualityResult,
    verdict: event_opportunity_verdict.OpportunityVerdict,
    opportunity_level: str,
    identity_rejection: str | None,
) -> dict[str, Any]:
    level = "local_only" if identity_rejection else opportunity_level
    return {
        "row_type": "event_impact_hypothesis",
        "hypothesis_id": f"signal-quality:{incident_id}",
        "incident_id": incident_id,
        "validated_symbol": None if identity_rejection else symbol,
        "validated_coin_id": None if identity_rejection else coin_id,
        "candidate_symbols": (symbol,) if symbol else (),
        "candidate_coin_ids": (coin_id,) if coin_id else (),
        "candidate_sectors": ("tokenized_stock_venues",) if not symbol and str(getattr(hypothesis, "impact_category", "")).endswith("_proxy") else (),
        "impact_category": getattr(hypothesis, "impact_category", None),
        "impact_path_type": impact.impact_path_type,
        "impact_path_strength": impact.impact_path_strength,
        "candidate_role": impact.candidate_role,
        "evidence_specificity": evidence.evidence_specificity,
        "source_class": evidence.source_class,
        "opportunity_level": level,
        "opportunity_score_final": 0.0 if identity_rejection else verdict.opportunity_score_final,
        "why_local_only": identity_rejection or verdict.why_local_only,
        "why_not_watchlist": identity_rejection or verdict.why_not_watchlist,
    }
def _expected(case: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in dict(case.get("expected") or {}).items()}
def _diff_expected(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    diffs: list[str] = []
    stages: list[str] = []
    stage_by_key = {
        "impact_path_type": "impact_path",
        "candidate_role": "candidate_role",
        "evidence_specificity": "evidence_quality",
        "market_confirmation_level": "market_confirmation",
        "market_context_freshness_status": "market_freshness",
        "market_context_age_hours": "market_freshness",
        "freshness_cap_applied": "market_freshness",
        "opportunity_level": "opportunity_verdict",
        "route_tier": "routing",
        "digest_eligible": "routing",
        "watchlist_eligible": "routing",
        "high_priority_eligible": "routing",
        "reason_codes": "opportunity_verdict",
        "blocked_reason": "opportunity_verdict",
        "triggered_fade": "routing",
        "identity_rejection_reason": "identity",
        "claim_polarities": "claim_semantics",
        "cause_status": "cause_status",
        "event_archetype": "incident_identity",
        "primary_subject": "primary_subject",
        "affected_ecosystem": "candidate_role",
        "market_reaction_confirmed": "market_reaction_vs_cause",
        "causal_mechanism_confirmed": "market_reaction_vs_cause",
        "incident_relevance_status": "incident_relevance",
        "incident_relevance_score": "incident_relevance",
        "canonical_persistence_reason": "incident_relevance",
        "qualified_link_count": "incident_relevance",
        "weak_link_count": "incident_relevance",
        "quality_blocked_link_count": "incident_relevance",
        "unknown_role_link_count": "incident_relevance",
        "link_quality_reasons": "incident_relevance",
        "diagnostic_hidden_by_default": "incident_relevance",
        "external_context_hidden_by_default": "incident_relevance",
        "selected_main_frame_type": "catalyst_frame",
        "background_frame_count": "catalyst_frame",
        "negated_frame_count": "catalyst_frame",
        "frame_rule_disagreement": "catalyst_frame",
        "frame_disagreement_resolution": "catalyst_frame",
        "core_opportunity_id": "core_aggregation",
        "aggregation_status": "core_aggregation",
        "near_miss_inclusion": "near_miss",
        "card_group": "research_card",
        "brief_section": "operator_brief",
        "diagnostic_visibility": "diagnostics",
        "false_positive_reason": "false_positive_filter",
        "human_readable_reason": "reason_text",
        "frame_counter_status": "catalyst_frame",
    }
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        ok = _matches(expected_value, actual_value)
        if not ok:
            diffs.append(f"{key}: expected {expected_value!r}, actual {actual_value!r}")
            stages.append(stage_by_key.get(key, key))
    return diffs, list(dict.fromkeys(stages))
def _matches(expected: Any, actual: Any) -> bool:
    if isinstance(expected, list):
        if key_set := {str(item) for item in expected if not str(item).startswith("contains:")}:
            if str(actual) in key_set:
                return True
        contains = [str(item).split("contains:", 1)[1] for item in expected if str(item).startswith("contains:")]
        if contains:
            values = actual if isinstance(actual, (list, tuple, set)) else (actual,)
            return any(str(value) in contains for value in values)
        return False
    if isinstance(expected, str) and expected.startswith("contains:"):
        needle = expected.split("contains:", 1)[1]
        values = actual if isinstance(actual, (list, tuple, set)) else (actual,)
        return any(str(value) == needle for value in values)
    return expected == actual
def _identity_rejection_reason(raw: RawDiscoveredEvent, *, symbol: str | None, coin_id: str | None) -> str | None:
    text = " ".join(str(value or "") for value in (raw.title, raw.body)).casefold()
    sym = str(symbol or "").upper()
    if sym == "BTC" and "bitcoin world" in text and "$btc" not in text and "btcusdt" not in text:
        return "publisher_source_name_not_asset_identity"
    if sym == "XRP" and "ripple effects" in text and "$xrp" not in text and "xrpusdt" not in text:
        return "common_phrase_not_asset_identity"
    if sym == "PRIME" and "prime minister" in text:
        return "common_word_or_title_not_asset_identity"
    if sym == "HYPE" and "hyperliquid" not in text and "$hype" not in text and "hypeusdt" not in text:
        return "generic_symbol_without_project_identity"
    return None
def _route_tier(level: str) -> str:
    return {
        "local_only": "STORE_ONLY",
        "exploratory": "STORE_ONLY",
        "validated_digest": "RADAR_DIGEST",
        "watchlist": "WATCHLIST",
        "high_priority": "HIGH_PRIORITY",
    }.get(level, "STORE_ONLY")
def _near_miss_status(level: str, route_tier: str, identity_rejection: str | None) -> str:
    if identity_rejection:
        return "diagnostic_not_near_miss"
    if level in {"validated_digest", "watchlist", "high_priority"} or route_tier in {
        "RADAR_DIGEST",
        "WATCHLIST",
        "HIGH_PRIORITY",
    }:
        return "excluded_already_promoted"
    return "eligible_if_close_to_threshold"
def _card_group(level: str, route_tier: str, identity_rejection: str | None) -> str:
    if identity_rejection:
        return "diagnostic_control"
    if level in {"validated_digest", "watchlist", "high_priority"} or route_tier in {
        "RADAR_DIGEST",
        "WATCHLIST",
        "HIGH_PRIORITY",
    }:
        return "core_opportunity"
    return "local_only_quality_capped"
def _brief_section(
    *,
    opportunity_level: str,
    route_tier: str,
    identity_rejection: str | None,
    false_positive_reason: str,
) -> str:
    if identity_rejection or false_positive_reason not in {"", "none"}:
        return "diagnostics"
    if opportunity_level == "high_priority" or route_tier == "HIGH_PRIORITY":
        return "high_priority_core"
    if opportunity_level == "watchlist" or route_tier == "WATCHLIST":
        return "watchlist_core"
    if opportunity_level == "validated_digest" or route_tier == "RADAR_DIGEST":
        return "validated_digest_core"
    if opportunity_level == "exploratory":
        return "near_miss"
    return "local_only_quality_capped"
def _diagnostic_visibility(brief_section: str) -> str:
    if brief_section == "diagnostics":
        return "hidden_by_default"
    if brief_section.endswith("_core"):
        return "main_section"
    return "review_section"
def _false_positive_reason(
    *,
    identity_rejection: str | None,
    impact_path_type: str,
    candidate_role: str,
    incident_relevance_status: str,
    source_class: str,
) -> str:
    text = " ".join(str(value or "") for value in (
        identity_rejection,
        impact_path_type,
        candidate_role,
        incident_relevance_status,
        source_class,
    )).casefold()
    if identity_rejection:
        if "publisher" in text or "source_name" in text or "source_origin" in text:
            return "source_noise"
        if "common" in text or "generic_symbol" in text or "ticker" in text:
            return "ticker_collision"
        return "identity_low_confidence"
    if "source_noise" in text or "publisher_suffix_false_positive" in text:
        return "source_noise"
    if "ticker_word_collision" in text:
        return "ticker_collision"
    if impact_path_type == "generic_cooccurrence_only":
        return "generic_cooccurrence_only"
    return "none"
def _human_readable_reason(
    blocked: Any,
    identity_rejection: str | None,
    reason_codes: Iterable[Any],
) -> str:
    if blocked not in (None, "", [], ()):
        values = blocked if isinstance(blocked, (list, tuple, set)) else (blocked,)
        return event_alpha_reason_text.humanize_event_alpha_reasons(values, limit=2)
    if identity_rejection:
        return event_alpha_reason_text.humanize_event_alpha_reason(identity_rejection)
    return event_alpha_reason_text.humanize_event_alpha_reasons(reason_codes, limit=2) or "qualified core opportunity"
def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
def _parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
def _compact(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, default=str)[:1200]
