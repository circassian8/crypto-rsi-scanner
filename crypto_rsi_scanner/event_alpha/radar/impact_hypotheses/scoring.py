"""Impact-hypothesis scoring and market-context helpers."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .... import (
    config,
)
import crypto_rsi_scanner.event_alpha.radar.catalyst_frames as event_catalyst_frames
import crypto_rsi_scanner.event_alpha.radar.claim_semantics as event_claim_semantics
import crypto_rsi_scanner.event_alpha.radar.evidence_quality as event_evidence_quality
import crypto_rsi_scanner.event_alpha.radar.graph as event_graph
import crypto_rsi_scanner.event_alpha.radar.identity as event_identity
import crypto_rsi_scanner.event_alpha.radar.incident_graph as event_incident_graph
import crypto_rsi_scanner.event_alpha.radar.impact_path_validator as event_impact_path_validator
import crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames as event_llm_catalyst_frames
from ..llm.extractor import EventLLMExtractionReportRow
from crypto_rsi_scanner.event_core.models import EventDiscoveryResult, NormalizedEvent, RawDiscoveredEvent
from ..resolver import clean_text
from .. import incidents as event_incident_store
from .. import market_confirmation as event_market_confirmation
from .. import opportunity_verdict as event_opportunity_verdict
from .models import (
    EventImpactHypothesis,
    HypothesisScope,
    HypothesisStatus,
    ImpactCategory,
    ImpactPathReason,
    ValidationStage,
)



def resolve_hypothesis_market_context(
    hypothesis: object,
    discovery_result: object | None = None,
    current_cycle_market_rows: Iterable[Mapping[str, Any]] = (),
    active_watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    targeted_provider: object | None = None,
    *,
    raw_event: RawDiscoveredEvent | None = None,
    validated_coin_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve market context for a hypothesis using a deterministic fallback order."""
    observed = _as_utc(now or datetime.now(timezone.utc))
    coin_id = clean_text(
        validated_coin_id
        or _first_asset_value(getattr(hypothesis, "validated_candidate_assets", ()) or (), "coin_id")
        or (getattr(hypothesis, "candidate_coin_ids", ()) or ("",))[0]
    )
    symbol = clean_text(
        _first_asset_value(getattr(hypothesis, "validated_candidate_assets", ()) or (), "symbol")
        or (getattr(hypothesis, "candidate_symbols", ()) or ("",))[0]
    )
    if raw_event is not None:
        snapshot = _market_snapshot_from_raw(raw_event)
        if snapshot:
            return _market_context_row(snapshot, source="candidate_event_market_snapshot", now=observed)
    for raw in getattr(discovery_result, "raw_events", ()) or ():
        if not isinstance(raw, RawDiscoveredEvent):
            continue
        if _raw_matches_asset(raw, coin_id=coin_id, symbol=symbol):
            snapshot = _market_snapshot_from_raw(raw)
            if snapshot:
                return _market_context_row(snapshot, source="discovery_candidate_market_snapshot", now=observed)
    for row in current_cycle_market_rows:
        if _row_matches_asset(row, coin_id=coin_id, symbol=symbol):
            return _market_context_row(dict(row), source="current_cycle_market_row", now=observed)
    for row in active_watchlist_rows:
        data = row if isinstance(row, Mapping) else getattr(row, "__dict__", {}) or {}
        if not _row_matches_asset(data, coin_id=coin_id, symbol=symbol):
            continue
        snapshot = data.get("latest_market_snapshot") if isinstance(data.get("latest_market_snapshot"), Mapping) else {}
        if snapshot:
            return _market_context_row(dict(snapshot), source="active_watchlist_market_snapshot", now=observed)
    if targeted_provider is not None and coin_id:
        try:
            rows = targeted_provider.fetch_market_rows((coin_id,))  # type: ignore[attr-defined]
        except Exception:
            rows = ()
        for row in rows or ():
            if isinstance(row, Mapping) and _row_matches_asset(row, coin_id=coin_id, symbol=symbol):
                return _market_context_row(dict(row), source="targeted_market_lookup", now=observed)
    return {
        "market_snapshot": {},
        "source": "missing",
        "timestamp": None,
        "age_seconds": None,
        "age_hours": None,
        "freshness_status": "missing",
        "stale": False,
        "data_quality": "missing",
        "missing_fields": ("market_snapshot", "current_cycle_market_row", "targeted_market_lookup"),
    }


def _market_snapshot_from_raw(raw: RawDiscoveredEvent) -> dict[str, Any]:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
    snapshot = dict(market)
    for key, value in anomaly.items():
        snapshot.setdefault(key, value)
    if snapshot:
        snapshot.setdefault("market_context_source", f"{raw.provider or 'raw'}_market_snapshot")
        if not any(
            key in snapshot
            for key in (
                "market_context_observed_at",
                "market_context_timestamp",
                "timestamp",
                "market_timestamp",
                "observed_at",
                "fetched_at",
            )
        ):
            snapshot["observed_at"] = raw.fetched_at.isoformat() if raw.fetched_at else None
    return {key: value for key, value in snapshot.items() if value not in (None, "", [], {})}


def _market_context_row(snapshot: Mapping[str, Any], *, source: str, now: datetime) -> dict[str, Any]:
    timestamp = (
        snapshot.get("market_context_observed_at")
        or snapshot.get("market_context_timestamp")
        or snapshot.get("timestamp")
        or snapshot.get("market_timestamp")
        or snapshot.get("observed_at")
        or snapshot.get("fetched_at")
    )
    age = _age_seconds(timestamp, now)
    if age is None:
        quality = "unknown"
    elif age <= config.EVENT_MARKET_CONTEXT_MAX_AGE_HOURS * 3600:
        quality = "fresh"
    else:
        quality = "stale"
    return {
        "market_snapshot": dict(snapshot),
        "source": source,
        "timestamp": str(timestamp) if timestamp not in (None, "") else None,
        "age_seconds": age,
        "age_hours": None if age is None else round(age / 3600.0, 4),
        "freshness_status": quality,
        "stale": quality == "stale",
        "data_quality": quality,
        "missing_fields": tuple(_market_missing_fields(snapshot)),
    }


def _market_missing_fields(snapshot: Mapping[str, Any]) -> tuple[str, ...]:
    missing: list[str] = []
    if not any(key in snapshot for key in ("return_24h", "price_change_24h", "price_change_percentage_24h")):
        missing.append("return_24h")
    if not any(key in snapshot for key in ("volume_zscore_24h", "volume_zscore")):
        missing.append("volume_zscore_24h")
    if not any(key in snapshot for key in ("volume_to_market_cap", "volume_mcap", "volume_mcap_ratio")):
        missing.append("volume_to_market_cap")
    return tuple(missing)


def _age_seconds(timestamp: Any, now: datetime) -> float | None:
    if timestamp in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    parsed = _as_utc(parsed)
    return max(0.0, (now - parsed).total_seconds())


def _raw_matches_asset(raw: RawDiscoveredEvent, *, coin_id: str, symbol: str) -> bool:
    payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
    market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
    return _row_matches_asset(market, coin_id=coin_id, symbol=symbol)


def _row_matches_asset(row: Mapping[str, Any], *, coin_id: str, symbol: str) -> bool:
    values = {
        clean_text(row.get("coin_id") or row.get("id") or ""),
        clean_text(row.get("symbol") or ""),
        clean_text(row.get("asset_symbol") or ""),
    }
    return bool((coin_id and coin_id in values) or (symbol and symbol in values))


def _first_asset_value(rows: Iterable[Mapping[str, Any]], key: str) -> str | None:
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return None


def _causal_mechanism_confirmed(
    validation: event_impact_path_validator.ImpactPathValidation,
    hypothesis: EventImpactHypothesis,
) -> bool:
    if validation.impact_path_type == event_impact_path_validator.ImpactPathType.MARKET_DISLOCATION_UNKNOWN.value:
        return False
    if validation.cause_status == event_claim_semantics.CauseStatus.RULED_OUT.value:
        return False
    if validation.cause_status == event_claim_semantics.CauseStatus.CONFIRMED.value:
        return True
    return validation.impact_path_strength in {"strong", "medium"} and validation.impact_path_reason not in {
        "cause_unknown_market_dislocation",
        "alleged_exploit_unconfirmed",
        "weak_cooccurrence_only",
        "generic_policy_only",
    }


def _quality_score_components(values: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    mapping = {
        "evidence_quality_score": "evidence_quality_score",
        "source_class": "source_class",
        "evidence_specificity": "evidence_specificity",
        "market_confirmation_score": "market_confirmation_score",
        "market_confirmation_level": "market_confirmation_level",
        "market_context_source": "market_context_source",
        "market_context_timestamp": "market_context_timestamp",
        "market_context_observed_at": "market_context_observed_at",
        "market_context_age_seconds": "market_context_age_seconds",
        "market_context_age_hours": "market_context_age_hours",
        "market_context_stale": "market_context_stale",
        "market_context_freshness_status": "market_context_freshness_status",
        "market_context_freshness_cap_applied": "market_context_freshness_cap_applied",
        "market_context_data_quality": "market_context_data_quality",
        "incident_market_reaction_observed": "incident_market_reaction_observed",
        "market_reaction_confirmed": "market_reaction_confirmed",
        "causal_mechanism_confirmed": "causal_mechanism_confirmed",
        "incident_causal_mechanism_confirmed": "incident_causal_mechanism_confirmed",
        "incident_confidence": "incident_confidence",
        "opportunity_score_final": "opportunity_score_final",
        "opportunity_level": "opportunity_level",
        "why_local_only": "why_local_only",
        "why_not_watchlist": "why_not_watchlist",
    }
    for source_key, target_key in mapping.items():
        value = values.get(source_key)
        if value not in (None, "", [], {}):
            out[target_key] = value
    out["market_confirmation"] = max(
        _coerce_score(out.get("market_confirmation_score")),
        _coerce_score(values.get("market_confirmation_score")),
    )
    out["source_quality"] = max(
        _coerce_score(out.get("evidence_quality_score")),
        _coerce_score(values.get("evidence_quality_score")),
    )
    for key in (
        "market_confirmation_reasons",
        "market_confirmation_warnings",
        "market_confirmation_missing_fields",
        "evidence_quality_reasons",
        "opportunity_verdict_reasons",
        "missing_requirements",
        "manual_verification_items",
        "role_evidence",
        "claim_polarities",
    ):
        value = values.get(key)
        if value:
            out[key] = list(value) if not isinstance(value, str) else [value]
    return out


def _payload_mapping(payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _coerce_score(value: object) -> float:
    try:
        return max(0.0, min(100.0, float(value or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _optional_score(value: object) -> float | None:
    score = _coerce_score(value)
    return score if score > 0 else None


def _identity_match_from_symbols(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> event_identity.IdentityMatchResult:
    strong = (raw.title, raw.body, _event_name(raw))
    for idx, symbol in enumerate(hypothesis.candidate_symbols):
        coin_id = hypothesis.candidate_coin_ids[idx] if idx < len(hypothesis.candidate_coin_ids) else None
        identity = event_identity.AssetIdentity(
            symbol=symbol,
            coin_id=coin_id,
            project_name=None,
            aliases=(coin_id.replace("-", " ") if coin_id else ""),
            is_common_word_symbol=symbol.upper() in event_identity.COMMON_WORD_SYMBOLS,
        )
        result = event_identity.match_asset_identity(
            identity,
            event_identity.IdentityEvidence(
                strong_content=tuple(str(item or "") for item in strong),
                url=raw.source_url,
                source_origin=(raw.provider,),
            ),
        )
        if result.matched or result.reason in {
            "common_word_identity_rejected",
            "identity_url_only_rejected",
            "identity_source_origin_rejected",
        }:
            return result
    return event_identity.IdentityMatchResult(False, event_identity.STRENGTH_NONE, None)


def _matched_symbol_and_coin_id(raw: RawDiscoveredEvent, hypothesis: EventImpactHypothesis) -> tuple[str | None, str | None]:
    strong = (raw.title, raw.body, _event_name(raw))
    for idx, symbol in enumerate(hypothesis.candidate_symbols):
        coin_id = hypothesis.candidate_coin_ids[idx] if idx < len(hypothesis.candidate_coin_ids) else None
        identity = event_identity.AssetIdentity(
            symbol=symbol,
            coin_id=coin_id,
            project_name=None,
            aliases=(coin_id.replace("-", " ") if coin_id else ""),
            is_common_word_symbol=symbol.upper() in event_identity.COMMON_WORD_SYMBOLS,
        )
        result = event_identity.match_asset_identity(
            identity,
            event_identity.IdentityEvidence(
                strong_content=tuple(str(item or "") for item in strong),
                url=raw.source_url,
                source_origin=(raw.provider,),
            ),
        )
        if result.matched:
            return symbol, coin_id
    return None, None


def _text_mentions_catalyst(text: str, hypothesis: EventImpactHypothesis) -> bool:
    external = clean_text(hypothesis.external_asset or "")
    if external and _term_hit(text, external):
        return True
    category_terms = {
        ImpactCategory.RWA_PREIPO_PROXY.value: ("pre ipo", "pre-ipo", "tokenized stock", "synthetic exposure"),
        ImpactCategory.AI_IPO_PROXY.value: ("openai", "anthropic", "pre ipo", "pre-ipo"),
        ImpactCategory.SPORTS_FAN_PROXY.value: ("world cup", "fan token", "fixture", "kickoff", "sports event"),
        ImpactCategory.STABLECOIN_REGULATORY.value: ("genius act", "stablecoin", "reserve"),
        ImpactCategory.PREDICTION_MARKET_INFRA.value: ("prediction market", "oracle"),
        ImpactCategory.PERP_VENUE_ATTENTION.value: ("perp", "futures listing"),
        ImpactCategory.LISTING_LIQUIDITY_EVENT.value: ("listing", "listed on"),
        ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value: ("unlock", "vesting", "airdrop"),
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value: (
            "exploit",
            "hack",
            "lawsuit",
            "regulatory",
            "quantum",
            "technology risk",
            "policy shock",
        ),
    }.get(hypothesis.impact_category, ())
    return _any_term_hit(text, category_terms)


def _text_mentions_candidate(text: str, hypothesis: EventImpactHypothesis) -> bool:
    return _any_term_hit(text, hypothesis.candidate_symbols)


def _category_validation_rejection(text: str, hypothesis: EventImpactHypothesis) -> str | None:
    category = str(hypothesis.impact_category or "")
    if category == ImpactCategory.POLITICAL_MEME_PROXY.value and not _has_political_context(text):
        if _any_term_hit(text, ("prediction market", "polymarket", "arbitrum", "ethereum", "tokenized equity")):
            return "political_context_missing_for_prediction_market_validation"
    if category == ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value and not _has_security_or_regulatory_context(text):
        if _any_term_hit(text, ("nasdaq listing", "public listing", "ipo listing", "listed on", "miner listing")):
            return "security_or_regulatory_context_missing_for_listing_validation"
    return None


def _hypothesis_score_components(
    event: NormalizedEvent,
    rule: Mapping[str, Any],
    text: str,
    raws: tuple[RawDiscoveredEvent, ...],
    cluster: event_graph.EventCluster | None,
    *,
    crypto_candidate_assets: tuple[dict[str, Any], ...],
    validated_assets: tuple[dict[str, Any], ...],
    suggested_assets: tuple[dict[str, Any], ...],
) -> dict[str, float]:
    source_conf = max((float(raw.source_confidence or 0.0) for raw in raws), default=float(event.confidence or 0.0))
    keyword_hits = sum(
        1 for keyword in (*rule.get("keywords", ()), *rule.get("secondary", ()))
        if _term_hit(text, str(keyword))
    )
    market_confirmation = _market_confirmation_score(raws)
    components = {
        "event_clarity": round(max(float(event.confidence or 0.0), source_conf) * 100, 2),
        "source_quality": round(source_conf * 100, 2),
        "catalyst_strength": round(min(100.0, 35.0 + keyword_hits * 12.0 + (15.0 if event.external_asset else 0.0)), 2),
        "sector_relevance": 80.0 if rule.get("sectors") else 35.0,
        "candidate_asset_strength": round(min(100.0, len(crypto_candidate_assets) * 18.0 + (35.0 if suggested_assets else 0.0)), 2),
        "validation_strength": 95.0 if validated_assets else 0.0,
        "market_confirmation": round(market_confirmation, 2),
        "cluster_confidence": round(max(0.0, min(100.0, float(getattr(cluster, "cluster_confidence", 0) or 0))), 2),
    }
    if event.event_time is not None:
        components["event_time_quality"] = round(max(0.0, min(100.0, float(event.event_time_confidence or 0.0) * 100)), 2)
    if suggested_assets:
        components["llm_candidate_confidence"] = round(max(float(row.get("confidence") or 0.0) for row in suggested_assets) * 100, 2)
    return components


def _weighted_hypothesis_score(components: Mapping[str, float], category: str) -> float:
    weights = {
        "event_clarity": 0.18,
        "source_quality": 0.12,
        "catalyst_strength": 0.18,
        "sector_relevance": 0.10,
        "candidate_asset_strength": 0.14,
        "validation_strength": 0.16,
        "market_confirmation": 0.08,
        "cluster_confidence": 0.04,
    }
    score = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        score += max(0.0, min(100.0, float(components.get(key) or 0.0))) * weight
        weight_sum += weight
    if components.get("event_time_quality") is not None:
        score += max(0.0, min(100.0, float(components.get("event_time_quality") or 0.0))) * 0.04
        weight_sum += 0.04
    if components.get("impact_path_strength") is not None:
        score += max(0.0, min(100.0, float(components.get("impact_path_strength") or 0.0))) * 0.08
        weight_sum += 0.08
    if components.get("llm_candidate_confidence") is not None:
        score += max(0.0, min(100.0, float(components.get("llm_candidate_confidence") or 0.0))) * 0.05
        weight_sum += 0.05
    final = score / max(0.01, weight_sum)
    if category == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        final = min(final, 55.0)
    return max(0.0, min(100.0, final))


def _market_confirmation_score(raws: Iterable[RawDiscoveredEvent]) -> float:
    best = 0.0
    for raw in raws:
        payload = raw.raw_json if isinstance(raw.raw_json, Mapping) else {}
        anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
        market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
        candidates = (
            ("anomaly_score", anomaly.get("score")),
            ("market_move_volume", market.get("market_move_volume")),
            ("volume_zscore_24h", market.get("volume_zscore_24h")),
            ("return_24h", market.get("return_24h")),
        )
        for key, value in candidates:
            if isinstance(value, bool):
                continue
            try:
                number = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(number):
                continue
            if key != "anomaly_score" and abs(number) <= 3.0:
                number *= 25.0
            best = max(best, number)
    return max(0.0, min(100.0, best))


def _initial_validation_stage(
    category: str,
    crypto_candidate_assets: tuple[dict[str, Any], ...],
    validated_assets: tuple[dict[str, Any], ...],
) -> str:
    if validated_assets and category != ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        return ValidationStage.CATALYST_LINK_VALIDATED.value
    if crypto_candidate_assets and category != ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        return ValidationStage.VALIDATION_SEARCH_PENDING.value
    if crypto_candidate_assets:
        return ValidationStage.CANDIDATE_ASSETS_SUGGESTED.value
    return ValidationStage.SECTOR_HYPOTHESIS.value


def _hypothesis_confidence(
    event: NormalizedEvent,
    rule: Mapping[str, Any],
    text: str,
    raws: tuple[RawDiscoveredEvent, ...],
    cluster: event_graph.EventCluster | None,
) -> float:
    source_conf = max((raw.source_confidence for raw in raws), default=event.confidence)
    score = 0.30 + 0.35 * max(float(event.confidence or 0.0), float(source_conf or 0.0))
    if event.external_asset:
        score += 0.08
    if event.event_time is not None:
        score += 0.06 * float(event.event_time_confidence or 0.0)
    keyword_hits = sum(1 for keyword in (*rule.get("keywords", ()), *rule.get("secondary", ())) if _term_hit(text, str(keyword)))
    score += min(0.16, keyword_hits * 0.035)
    if cluster is not None:
        score += min(0.12, max(0, cluster.cluster_confidence) / 1000)
    if rule.get("category") == ImpactCategory.MARKET_ANOMALY_UNKNOWN:
        score = min(score, 0.55)
    return max(0.0, min(1.0, round(score, 4)))


def _hypothesis_warnings(
    event: NormalizedEvent,
    raws: tuple[RawDiscoveredEvent, ...],
    category: str,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not event.external_asset and category not in {
        ImpactCategory.LISTING_LIQUIDITY_EVENT.value,
        ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION.value,
        ImpactCategory.UNLOCK_SUPPLY_PRESSURE.value,
        ImpactCategory.MARKET_ANOMALY_UNKNOWN.value,
        ImpactCategory.SECURITY_OR_REGULATORY_SHOCK.value,
    }:
        warnings.append("external catalyst inferred from source text only")
    if not raws:
        warnings.append("no raw source evidence attached")
    if category == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        warnings.append("no confirmed catalyst; keep store-only until source evidence appears")
    return tuple(warnings)


def _validation_steps(category: str) -> tuple[str, ...]:
    common = (
        "find independent source evidence that names a candidate asset",
        "validate candidate identity outside URL/source-origin fields",
        "confirm the source explicitly links candidate asset to catalyst or sector",
    )
    if category in {
        ImpactCategory.RWA_PREIPO_PROXY.value,
        ImpactCategory.AI_IPO_PROXY.value,
        ImpactCategory.TOKENIZED_STOCK_VENUE.value,
    }:
        return (*common, "verify the asset is proxy venue/instrument rather than publisher noise")
    if category == ImpactCategory.MARKET_ANOMALY_UNKNOWN.value:
        return ("find independent catalyst evidence", "verify move is not purely liquidity/noise")
    if category == ImpactCategory.STRATEGIC_INVESTMENT_OR_VALUATION.value:
        return (*common, "verify the investment/stake/valuation is current and token/protocol-specific")
    return common
