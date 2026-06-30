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
    query_intents: tuple[str, ...] = ()
    official_confirmation_queries: tuple[EvidencePlanQuery, ...] = ()
    denial_correction_queries: tuple[EvidencePlanQuery, ...] = ()
    expected_proof_criteria: tuple[str, ...] = ()
    manual_checklist: tuple[str, ...] = ()
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
            "evidence_query_intents": self.query_intents,
            "evidence_official_confirmation_queries": tuple(item.to_metadata() for item in self.official_confirmation_queries),
            "evidence_denial_correction_queries": tuple(item.to_metadata() for item in self.denial_correction_queries),
            "evidence_expected_proof_criteria": self.expected_proof_criteria,
            "evidence_manual_checklist": self.manual_checklist,
            "evidence_provider_gaps": self.provider_gaps,
            "evidence_acquisition_warnings": self.warnings,
        }


@dataclass(frozen=True)
class EvidenceContradictionStatus:
    status: str
    blocks_validation: bool
    reason: str
    denial_queries: tuple[EvidencePlanQuery, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "contradiction_status": self.status,
            "contradiction_blocks_validation": self.blocks_validation,
            "contradiction_reason": self.reason,
            "contradiction_denial_queries": tuple(item.to_metadata() for item in self.denial_queries),
            "contradiction_warnings": self.warnings,
        }


@dataclass(frozen=True)
class EventAnalystSummary:
    why_surfaced: str
    why_not_alertable: str
    what_would_upgrade: str
    what_would_invalidate: str
    what_to_check_next: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "analyst_summary_why_surfaced": self.why_surfaced,
            "analyst_summary_why_not_alertable": self.why_not_alertable,
            "analyst_summary_what_would_upgrade": self.what_would_upgrade,
            "analyst_summary_what_would_invalidate": self.what_would_invalidate,
            "analyst_summary_check_next": self.what_to_check_next,
            "analyst_summary_warnings": self.warnings,
        }


@dataclass(frozen=True)
class LLMAnalystToolBudgetConfig:
    enabled: bool = True
    provider: str = "fixture"
    api_key_present: bool = False
    max_calls_per_run: int = 20


@dataclass(frozen=True)
class LLMAnalystToolBudgetResult:
    triage_llm_calls: int = 0
    query_planner_llm_calls: int = 0
    summary_llm_calls: int = 0
    skipped_by_budget: int = 0
    skipped_missing_api_key: int = 0
    selected_row_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "triage_llm_calls": self.triage_llm_calls,
            "query_planner_llm_calls": self.query_planner_llm_calls,
            "summary_llm_calls": self.summary_llm_calls,
            "skipped_by_budget": self.skipped_by_budget,
            "skipped_missing_api_key": self.skipped_missing_api_key,
            "selected_row_ids": self.selected_row_ids,
            "warnings": self.warnings,
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
        provider_health=_provider_health_from_row(merged),
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
    query_intents = tuple(dict.fromkeys(query.purpose for query in (*queries, *denial) if query.purpose))
    checklist = _checklist(request, pack)
    warnings: list[str] = []
    if pack.name in {"political_meme_pack", "proxy_preipo_rwa_pack"} and "polymarket" in " ".join(pack.preferred_providers):
        warnings.append("prediction_market_context_only_until_token_identity_validated")
    if not selected:
        warnings.append("planner_not_selected_below_prefilter")
    contradiction = detect_contradiction_or_denial(request)
    if contradiction.blocks_validation:
        warnings.extend(contradiction.warnings or (contradiction.reason,))
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
        checklist=checklist,
        query_intents=query_intents,
        official_confirmation_queries=official,
        denial_correction_queries=denial,
        expected_proof_criteria=_expected_proof_criteria(request, pack),
        manual_checklist=checklist,
        provider_gaps=provider_gaps,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def detect_contradiction_or_denial(row_or_request: EvidencePlannerRequest | Mapping[str, Any]) -> EvidenceContradictionStatus:
    request = row_or_request if isinstance(row_or_request, EvidencePlannerRequest) else request_from_row(row_or_request)
    text = " ".join(str(part or "") for part in (
        request.event_name,
        request.external_asset,
        request.playbook_type,
        request.impact_path_type,
        " ".join(request.missing_evidence),
    )).casefold()
    if not text and isinstance(row_or_request, Mapping):
        text = " ".join(str(row_or_request.get(key) or "") for key in (
            "title", "body", "description", "reason", "llm_reason", "impact_path_reason", "event_name",
        )).casefold()
    pack = event_source_packs.source_pack_for_playbook(
        request.playbook_type,
        impact_path_type=request.impact_path_type,
    )
    queries = _denial_queries(request, pack)
    exploit_denial = any(term in text for term in (
        "not hacked", "no hack", "no exploit", "false exploit", "exploit denied", "hack denied",
    ))
    listing_denial = any(term in text for term in (
        "denies listing", "listing denied", "not listing", "fake listing", "false listing",
    ))
    partnership_denial = any(term in text for term in (
        "denies partnership", "partnership denied", "not affiliated", "no affiliation", "rumor denied",
    ))
    correction = any(term in text for term in ("correction", "corrected", "clarifies", "clarification"))
    rumor = any(term in text for term in ("rumor", "rumoured", "unconfirmed", "unofficial source"))
    if exploit_denial and pack.name == "security_shock_pack":
        return EvidenceContradictionStatus(
            status="denial_found",
            blocks_validation=True,
            reason="exploit_or_hack_denied",
            denial_queries=queries,
            warnings=("exploit_denial_blocks_security_path",),
        )
    if listing_denial and pack.name in {"listing_liquidity_pack", "perp_listing_squeeze_pack"}:
        return EvidenceContradictionStatus(
            status="denial_found",
            blocks_validation=True,
            reason="listing_denied_or_fake",
            denial_queries=queries,
            warnings=("listing_denial_blocks_listing_path",),
        )
    if partnership_denial:
        return EvidenceContradictionStatus(
            status="denial_found",
            blocks_validation=True,
            reason="partnership_or_affiliation_denied",
            denial_queries=queries,
            warnings=("relationship_denial_blocks_candidate",),
        )
    if correction:
        return EvidenceContradictionStatus(
            status="correction_risk",
            blocks_validation=True,
            reason="source_correction_requires_review",
            denial_queries=queries,
            warnings=("correction_requires_manual_review",),
        )
    if rumor:
        return EvidenceContradictionStatus(
            status="rumor_or_unofficial",
            blocks_validation=False,
            reason="rumor_needs_denial_and_official_confirmation_search",
            denial_queries=queries,
            warnings=("unofficial_or_rumor_source",),
        )
    return EvidenceContradictionStatus(
        status="none_detected",
        blocks_validation=False,
        reason="no_denial_or_correction_terms_detected",
        denial_queries=queries,
        warnings=(),
    )


def generate_analyst_summary(row: Mapping[str, Any], *, plan: EvidencePlannerResult | Mapping[str, Any] | None = None) -> EventAnalystSummary:
    request = request_from_row(row)
    plan_meta = plan.to_metadata() if isinstance(plan, EvidencePlannerResult) else dict(plan or {})
    level = request.opportunity_level or str(row.get("final_opportunity_level") or "local_only")
    final_route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").strip()
    impact = request.impact_path_type or str(row.get("impact_category") or "unknown")
    source_pack = str(plan_meta.get("evidence_acquisition_source_pack") or row.get("source_pack") or request.source_pack or "unknown")
    symbol = request.symbol or request.coin_id or "candidate"
    score = request.score
    why_surfaced = (
        f"{symbol} surfaced as {level} under {impact} with score {score:.1f}"
        if score
        else f"{symbol} surfaced as {level} under {impact}"
    )
    block_reason = str(
        row.get("quality_gate_block_reason")
        or row.get("why_not_promoted")
        or row.get("why_not_watchlist")
        or row.get("why_local_only")
        or ""
    )
    if final_route and final_route not in {"RESEARCH_DIGEST", "WATCHLIST", "HIGH_PRIORITY_RESEARCH", "TRIGGERED_FADE_RESEARCH"}:
        why_not_alertable = f"Not alertable on final route {final_route}"
        if block_reason:
            why_not_alertable += f": {_first_text(block_reason)}"
    elif level in {"local_only", "exploratory"}:
        why_not_alertable = f"Not alertable because opportunity level is {level}"
        if block_reason:
            why_not_alertable += f": {_first_text(block_reason)}"
    else:
        why_not_alertable = "Alertability is governed by deterministic route, source-pack, and quality gates."
    needed = _iter_texts(plan_meta.get("evidence_needed") or row.get("missing_requirements") or row.get("upgrade_requirements"))
    criteria = _iter_texts(plan_meta.get("evidence_expected_proof_criteria") or plan_meta.get("evidence_validation_criteria"))
    upgrade_parts = tuple(dict.fromkeys((*needed[:3], *criteria[:2])))
    what_would_upgrade = (
        "source/evidence proof: " + "; ".join(upgrade_parts)
        if upgrade_parts
        else "accepted source-pack evidence plus fresh market confirmation"
    )
    contradiction = detect_contradiction_or_denial(row)
    if contradiction.blocks_validation:
        what_would_invalidate = contradiction.reason
    elif source_pack in {"proxy_preipo_rwa_pack", "ai_ipo_proxy_pack"}:
        what_would_invalidate = "proxy/exposure denied, source corrected, or market confirmation fails"
    elif source_pack == "security_shock_pack":
        what_would_invalidate = "exploit/security claim denied or unrelated to the asset"
    elif source_pack in {"listing_liquidity_pack", "perp_listing_squeeze_pack"}:
        what_would_invalidate = "official listing denied, stale, or not tied to the token identity"
    else:
        what_would_invalidate = "source correction, missing token identity, or unsupported impact path"
    checklist = _iter_texts(plan_meta.get("evidence_manual_checklist") or plan_meta.get("evidence_acquisition_checklist"))
    check_next = tuple(dict.fromkeys(checklist[:4] or ("confirm source evidence", "verify asset identity", "refresh market context")))
    warnings = tuple(dict.fromkeys((
        *_iter_texts(row.get("warnings")),
        *_iter_texts(plan_meta.get("evidence_acquisition_warnings")),
        *contradiction.warnings,
    )))
    return EventAnalystSummary(
        why_surfaced=why_surfaced,
        why_not_alertable=why_not_alertable,
        what_would_upgrade=what_would_upgrade,
        what_would_invalidate=what_would_invalidate,
        what_to_check_next=check_next,
        warnings=warnings,
    )


def select_llm_analyst_tools(
    rows: Iterable[Mapping[str, Any]],
    *,
    cfg: LLMAnalystToolBudgetConfig | None = None,
) -> LLMAnalystToolBudgetResult:
    cfg = cfg or LLMAnalystToolBudgetConfig()
    if not cfg.enabled:
        return LLMAnalystToolBudgetResult(warnings=("llm_analyst_tools_disabled",))
    if cfg.provider != "fixture" and not cfg.api_key_present:
        rows_tuple = tuple(rows)
        return LLMAnalystToolBudgetResult(
            skipped_missing_api_key=len(rows_tuple),
            warnings=("missing_api_key",),
        )
    remaining = max(0, int(cfg.max_calls_per_run))
    triage = planner = summary = skipped = 0
    selected: list[str] = []
    for row in rows:
        needs = _analyst_tool_needs(row)
        if not needs:
            continue
        needed_calls = len(needs)
        if needed_calls > remaining:
            skipped += 1
            continue
        remaining -= needed_calls
        if "triage" in needs:
            triage += 1
        if "planner" in needs:
            planner += 1
        if "summary" in needs:
            summary += 1
        selected.append(_row_id(row))
    return LLMAnalystToolBudgetResult(
        triage_llm_calls=triage,
        query_planner_llm_calls=planner,
        summary_llm_calls=summary,
        skipped_by_budget=skipped,
        selected_row_ids=tuple(selected),
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
    elif pack.name == "project_event_pack":
        queries.append(EvidencePlanQuery(f"{symbol} project event calendar", "coinmarketcal", "event_time_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} mainnet upgrade official announcement", "project_blog_rss", "official_confirmation"))
    elif pack.name == "fan_sports_pack":
        queries.append(EvidencePlanQuery(f"{symbol} fan token {catalyst} match", "sports_fixtures", "event_time_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} fan token demand {catalyst}", "cryptopanic", "impact_path_validation"))
    elif pack.name == "strategic_investment_pack":
        queries.append(EvidencePlanQuery(f"{symbol} {catalyst} stake investment", "cryptopanic", "impact_path_validation"))
        queries.append(EvidencePlanQuery(f"{catalyst} {symbol} investment valuation", "gdelt", "second_source_confirmation"))
        queries.append(EvidencePlanQuery(f"{symbol} {catalyst} strategic investment official", "project_blog_rss", "official_confirmation"))
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
    if pack.name == "strategic_investment_pack":
        return (
            EvidencePlanQuery(f"{catalyst} denies {symbol} stake", "gdelt", "denial_search", must_validate_asset=False),
            EvidencePlanQuery(f"{symbol} {catalyst} stake confirmed", "gdelt", "denial_search", must_validate_asset=False),
        )
    return (EvidencePlanQuery(f"{symbol} catalyst denied corrected", "gdelt", "denial_search"),)


def _evidence_needed(request: EvidencePlannerRequest, pack: event_source_packs.SourcePack) -> tuple[str, ...]:
    values = list(pack.minimum_evidence)
    values.extend(reason for reason in request.missing_evidence if _refreshable_reason(reason))
    if request.frame_disagreement:
        values.append("resolve catalyst-frame disagreement")
    return tuple(dict.fromkeys(values))


def _expected_proof_criteria(request: EvidencePlannerRequest, pack: event_source_packs.SourcePack) -> tuple[str, ...]:
    criteria = list(pack.validation_requirements)
    if pack.name in {"proxy_preipo_rwa_pack", "ai_ipo_proxy_pack"}:
        criteria.extend([
            "source quote names the token/venue and the external exposure mechanism",
            "prediction-market context is not used as token-impact proof by itself",
        ])
    elif pack.name == "security_shock_pack":
        criteria.extend([
            "source confirms the incident affected the candidate asset/protocol",
            "denial/correction search does not rule out the exploit/security path",
        ])
    elif pack.name in {"listing_liquidity_pack", "perp_listing_squeeze_pack"}:
        criteria.extend([
            "official exchange announcement names the exact symbol/pair/contract",
            "market or derivatives refresh confirms the listing mattered for trading conditions",
        ])
    elif pack.name == "strategic_investment_pack":
        criteria.extend([
            "second source or official source confirms the stake/investment",
            "source explains why the stake or valuation is relevant to token value",
        ])
    if request.frame_disagreement:
        criteria.append("manual review resolves rule-vs-LLM catalyst frame disagreement")
    return tuple(dict.fromkeys(criteria))


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
    if pack.name == "strategic_investment_pack":
        base.append("check for denial, correction, or non-token equity-only interpretation")
    if pack.name == "security_shock_pack":
        base.append("check whether the exploit/security claim was denied or corrected")
    return tuple(dict.fromkeys(base))


def _analyst_tool_needs(row: Mapping[str, Any]) -> tuple[str, ...]:
    needs: list[str] = []
    level = str(row.get("opportunity_level") or row.get("final_opportunity_level") or "").casefold()
    route = str(row.get("final_route_after_quality_gate") or row.get("route") or "").casefold()
    score = _float(row.get("opportunity_score_final") or row.get("score")) or 0.0
    text = " ".join(str(row.get(key) or "") for key in (
        "title", "event_name", "canonical_incident_name", "body", "description", "impact_path_reason",
    )).casefold()
    if row.get("source_url") and (
        row.get("source_quality_score") in (None, "")
        or str(row.get("source_triage_decision") or "").casefold() in {"", "send_to_llm_frame_analyzer"}
    ):
        needs.append("triage")
    if should_plan_evidence(row) or any(term in text for term in ("denied", "not hacked", "correction", "rumor", "unofficial")):
        needs.append("planner")
    if level in {"validated_digest", "watchlist", "high_priority"} or "research" in route or score >= 50:
        needs.append("summary")
    return tuple(dict.fromkeys(needs))


def _row_id(row: Mapping[str, Any]) -> str:
    for key in ("core_opportunity_id", "hypothesis_id", "alert_id", "watchlist_key", "raw_id", "symbol", "coin_id"):
        value = row.get(key)
        if value:
            return str(value)
    return "unknown"


def _first_text(value: object) -> str:
    texts = _iter_texts(value)
    if not texts:
        return ""
    return texts[0][:180]


def _provider_gaps(provider_health: Mapping[str, Any]) -> tuple[str, ...]:
    gaps: list[str] = []
    for provider, status in provider_health.items():
        text = str(status.get("status") if isinstance(status, Mapping) else status).casefold()
        if text in {"degraded", "unavailable", "not_configured", "disabled", "missing_api_key"}:
            gaps.append(f"{provider}:{text}")
    return tuple(gaps)


def _provider_health_from_row(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("provider_health", "provider_health_by_source_pack", "source_provider_health"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    provider = str(row.get("provider") or row.get("source_provider") or "").strip()
    status = str(row.get("provider_coverage_status") or "").strip()
    if provider and status:
        return {provider: {"status": status}}
    return None


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
