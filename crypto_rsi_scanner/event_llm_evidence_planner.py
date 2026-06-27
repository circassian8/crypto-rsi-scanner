"""Constrained evidence planning for Event Alpha candidates.

The planner describes what evidence should be acquired next. It does not decide
alert tiers, execute searches, send notifications, or create event-fade signals.
The implementation is deterministic/fixture-friendly in Phase 1 so tests and
daily reports can use it without network or LLM credentials.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import event_source_packs


@dataclass(frozen=True)
class EvidencePlanQuery:
    query: str
    provider_hint: str
    purpose: str
    must_validate_asset: bool = True

    def to_metadata(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "provider_hint": self.provider_hint,
            "purpose": self.purpose,
            "must_validate_asset": self.must_validate_asset,
        }


@dataclass(frozen=True)
class EvidencePlannerRequest:
    opportunity_id: str
    symbol: str
    coin_id: str
    event_name: str = ""
    external_asset: str = ""
    playbook_type: str = ""
    impact_path_type: str = ""
    candidate_role: str = ""
    missing_evidence: tuple[str, ...] = ()
    provider_health: Mapping[str, Any] | None = None
    score: float = 0.0
    opportunity_level: str = "local_only"
    frame_disagreement: bool = False
    source_pack: str | None = None


@dataclass(frozen=True)
class EvidencePlannerResult:
    plan_id: str
    opportunity_id: str
    selected: bool
    source_pack: str
    evidence_needed: tuple[str, ...] = ()
    query_plan: tuple[EvidencePlanQuery, ...] = ()
    denial_searches: tuple[EvidencePlanQuery, ...] = ()
    official_searches: tuple[EvidencePlanQuery, ...] = ()
    market_refresh_requests: tuple[str, ...] = ()
    derivatives_refresh_requests: tuple[str, ...] = ()
    supply_refresh_requests: tuple[str, ...] = ()
    validation_criteria: tuple[str, ...] = ()
    checklist: tuple[str, ...] = ()
    provider_gaps: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "evidence_plan_id": self.plan_id,
            "evidence_acquisition_selected": self.selected,
            "evidence_acquisition_source_pack": self.source_pack,
            "evidence_needed": self.evidence_needed,
            "evidence_query_plan": tuple(item.to_metadata() for item in self.query_plan),
            "evidence_denial_searches": tuple(item.to_metadata() for item in self.denial_searches),
            "evidence_official_searches": tuple(item.to_metadata() for item in self.official_searches),
            "evidence_market_refresh_requests": self.market_refresh_requests,
            "evidence_derivatives_refresh_requests": self.derivatives_refresh_requests,
            "evidence_supply_refresh_requests": self.supply_refresh_requests,
            "evidence_validation_criteria": self.validation_criteria,
            "evidence_acquisition_checklist": self.checklist,
            "evidence_provider_gaps": self.provider_gaps,
            "evidence_acquisition_warnings": self.warnings,
        }


def request_from_row(
    row: Mapping[str, Any],
    *,
    missing_evidence: Iterable[str] = (),
    source_pack: str | None = None,
) -> EvidencePlannerRequest:
    components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
    latest = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
    merged = {**dict(components or {}), **dict(latest or {}), **dict(row)}
    symbol = str(merged.get("validated_symbol") or merged.get("symbol") or "").strip()
    coin_id = str(merged.get("validated_coin_id") or merged.get("coin_id") or "").strip()
    opportunity_id = str(
        merged.get("core_opportunity_id")
        or merged.get("hypothesis_id")
        or merged.get("key")
        or merged.get("alert_id")
        or symbol
        or coin_id
        or "unknown"
    )
    missing = tuple(dict.fromkeys(str(item) for item in (
        *tuple(missing_evidence),
        *_iter_texts(merged.get("missing_requirements")),
        *_iter_texts(merged.get("why_not_watchlist")),
        *_iter_texts(merged.get("why_local_only")),
    ) if str(item)))
    return EvidencePlannerRequest(
        opportunity_id=opportunity_id,
        symbol=symbol,
        coin_id=coin_id,
        event_name=str(merged.get("event_name") or merged.get("canonical_incident_name") or ""),
        external_asset=str(merged.get("external_asset") or ""),
        playbook_type=str(merged.get("playbook_type") or merged.get("latest_effective_playbook_type") or merged.get("impact_category") or ""),
        impact_path_type=str(merged.get("impact_path_type") or ""),
        candidate_role=str(merged.get("candidate_role") or ""),
        missing_evidence=missing,
        score=_float(merged.get("opportunity_score_final")) or _float(merged.get("score")) or 0.0,
        opportunity_level=str(merged.get("opportunity_level") or "local_only"),
        frame_disagreement=bool(merged.get("frame_rule_disagreement")),
        source_pack=source_pack or str(merged.get("source_pack") or ""),
    )


def should_plan_evidence(row: Mapping[str, Any]) -> bool:
    request = request_from_row(row)
    level = request.opportunity_level
    score = request.score
    if request.frame_disagreement:
        return True
    if level in {"validated_digest", "watchlist", "high_priority"}:
        return True
    if score >= 55 and any(_refreshable_reason(reason) for reason in request.missing_evidence):
        return True
    return False


def plan_evidence(request: EvidencePlannerRequest | Mapping[str, Any]) -> EvidencePlannerResult:
    if isinstance(request, Mapping):
        request = request_from_row(request)
    pack = event_source_packs.get_source_pack(request.source_pack) if request.source_pack else event_source_packs.source_pack_for_playbook(
        request.playbook_type,
        impact_path_type=request.impact_path_type,
    )
    selected = (
        request.opportunity_level in {"validated_digest", "watchlist", "high_priority"}
        or request.score >= 55
        or request.frame_disagreement
    )
    provider_gaps = _provider_gaps(request.provider_health or {})
    evidence_needed = _evidence_needed(request, pack)
    queries = _query_plan(request, pack)
    denial = _denial_queries(request, pack)
    official = tuple(query for query in queries if query.purpose in {"official_confirmation", "source_pack_official_search"})
    market = (request.coin_id or request.symbol,) if pack.market_refresh_required and (request.coin_id or request.symbol) else ()
    derivatives = (request.coin_id or request.symbol,) if pack.derivatives_refresh_required and (request.coin_id or request.symbol) else ()
    supply = (request.coin_id or request.symbol,) if pack.supply_refresh_required and (request.coin_id or request.symbol) else ()
    warnings: list[str] = []
    if pack.name in {"political_meme_pack", "proxy_preipo_rwa_pack"} and "polymarket" in " ".join(pack.preferred_providers):
        warnings.append("prediction_market_context_only_until_token_identity_validated")
    if not selected:
        warnings.append("planner_not_selected_below_prefilter")
    return EvidencePlannerResult(
        plan_id=_plan_id(request, pack.name),
        opportunity_id=request.opportunity_id,
        selected=selected,
        source_pack=pack.name,
        evidence_needed=evidence_needed,
        query_plan=queries,
        denial_searches=denial,
        official_searches=official,
        market_refresh_requests=market,
        derivatives_refresh_requests=derivatives,
        supply_refresh_requests=supply,
        validation_criteria=pack.validation_requirements,
        checklist=_checklist(request, pack),
        provider_gaps=provider_gaps,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _query_plan(request: EvidencePlannerRequest, pack: event_source_packs.SourcePack) -> tuple[EvidencePlanQuery, ...]:
    symbol = request.symbol or request.coin_id or "asset"
    catalyst = request.external_asset or request.event_name or request.impact_path_type or "catalyst"
    queries: list[EvidencePlanQuery] = []
    if pack.name == "security_shock_pack":
        queries.append(EvidencePlanQuery(f"{symbol} exploit official update", "project_blog_rss", "official_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} hack incident security market reaction", "cryptopanic", "second_source_confirmation"))
    elif pack.name in {"proxy_preipo_rwa_pack", "ai_ipo_proxy_pack"}:
        queries.append(EvidencePlanQuery(f"{symbol} {catalyst} exposure official", "project_blog_rss", "official_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} {catalyst} pre IPO tokenized stock", "cryptopanic", "impact_path_validation"))
        queries.append(EvidencePlanQuery(f"{catalyst} prediction market {symbol}", "polymarket", "external_context", must_validate_asset=False))
    elif pack.name == "listing_liquidity_pack":
        queries.append(EvidencePlanQuery(f"{symbol} listing announcement", "official_exchange", "official_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} trading start listing liquidity", "cryptopanic", "second_source_confirmation"))
    elif pack.name == "perp_listing_squeeze_pack":
        queries.append(EvidencePlanQuery(f"{symbol} perpetual futures listing announcement", "official_exchange", "official_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} funding open interest after perp listing", "coinalyze", "derivatives_confirmation"))
    elif pack.name == "unlock_supply_pack":
        queries.append(EvidencePlanQuery(f"{symbol} token unlock vesting schedule", "tokenomist", "supply_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} unlock official announcement", "project_blog_rss", "official_confirmation"))
    elif pack.name == "fan_sports_pack":
        queries.append(EvidencePlanQuery(f"{symbol} fan token {catalyst} match", "sports_fixtures", "event_time_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} fan token demand {catalyst}", "cryptopanic", "impact_path_validation"))
    else:
        queries.append(EvidencePlanQuery(f"{symbol} {catalyst} crypto catalyst why moving", "cryptopanic", "source_pack_search"))
        queries.append(EvidencePlanQuery(f"{symbol} {catalyst} official announcement catalyst", "project_blog_rss", "official_confirmation"))
    return tuple(queries)


def _denial_queries(request: EvidencePlannerRequest, pack: event_source_packs.SourcePack) -> tuple[EvidencePlanQuery, ...]:
    symbol = request.symbol or request.coin_id or "asset"
    catalyst = request.external_asset or request.event_name or request.impact_path_type or "catalyst"
    if pack.name in {"proxy_preipo_rwa_pack", "ai_ipo_proxy_pack"}:
        return (
            EvidencePlanQuery(f"{symbol} {catalyst} denies exposure", "gdelt", "denial_search", must_validate_asset=False),
            EvidencePlanQuery(f"{catalyst} not affiliated with {symbol}", "gdelt", "denial_search", must_validate_asset=False),
        )
    if pack.name == "security_shock_pack":
        return (EvidencePlanQuery(f"{symbol} no exploit false report", "gdelt", "denial_search"),)
    return (EvidencePlanQuery(f"{symbol} catalyst denied corrected", "gdelt", "denial_search"),)


def _evidence_needed(request: EvidencePlannerRequest, pack: event_source_packs.SourcePack) -> tuple[str, ...]:
    values = list(pack.minimum_evidence)
    values.extend(reason for reason in request.missing_evidence if _refreshable_reason(reason))
    if request.frame_disagreement:
        values.append("resolve catalyst-frame disagreement")
    return tuple(dict.fromkeys(values))


def _checklist(request: EvidencePlannerRequest, pack: event_source_packs.SourcePack) -> tuple[str, ...]:
    base = [
        "confirm token/project identity with non-URL evidence",
        "confirm catalyst and event timing",
        "verify the impact path explains why this token should move",
    ]
    if pack.market_refresh_required:
        base.append("refresh market move, volume, and liquidity context")
    if pack.derivatives_refresh_required:
        base.append("refresh funding/open-interest/crowding")
    if pack.supply_refresh_required:
        base.append("refresh unlock/supply pressure")
    if request.candidate_role in {"proxy_venue", "proxy_instrument"}:
        base.append("check denial/correction sources for proxy relationship")
    return tuple(dict.fromkeys(base))


def _provider_gaps(provider_health: Mapping[str, Any]) -> tuple[str, ...]:
    gaps: list[str] = []
    for provider, status in provider_health.items():
        text = str(status.get("status") if isinstance(status, Mapping) else status).casefold()
        if text in {"degraded", "unavailable", "not_configured", "disabled", "missing_api_key"}:
            gaps.append(f"{provider}:{text}")
    return tuple(gaps)


def _plan_id(request: EvidencePlannerRequest, source_pack: str) -> str:
    seed = "|".join((request.opportunity_id, request.symbol, request.coin_id, source_pack, request.external_asset, request.impact_path_type))
    return "evidence_plan:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]


def _refreshable_reason(reason: object) -> bool:
    text = str(reason or "").casefold()
    return any(part in text for part in ("source", "evidence", "impact", "market", "derivative", "supply", "identity", "coverage", "frame"))


def _iter_texts(value: object) -> tuple[str, ...]:
    if value in (None, "", [], {}, ()):
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Mapping):
        return tuple(f"{key}:{child}" for key, child in value.items())
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value if str(item))
    return (str(value),)


def _float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
