"""Core opportunity aggregation for Event Alpha operator-facing reports.

This module is presentation-only. It collapses compatible Event Alpha rows
into one visible opportunity while keeping control/source-noise rows available
as diagnostics. It does not score, route, send, trade, or mutate artifacts.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping

from . import event_alpha_quality_fields, event_alpha_router, event_playbooks, event_watchlist


@dataclass(frozen=True)
class CoreOpportunity:
    core_opportunity_id: str
    incident_id: str | None
    canonical_incident_name: str | None
    symbol: str
    coin_id: str
    candidate_role: str
    primary_impact_path: str
    opportunity_level: str
    opportunity_score_final: float
    final_route_after_quality_gate: str
    final_state_after_quality_gate: str
    supporting_hypothesis_ids: tuple[str, ...]
    supporting_categories: tuple[str, ...]
    supporting_impact_paths: tuple[str, ...]
    supporting_evidence_quotes: tuple[str, ...]
    diagnostic_row_count: int
    source_noise_control_count: int
    quality_capped_supporting_rows: int
    why_opportunity_visible: str
    why_other_rows_hidden: str
    primary_row: dict[str, Any]
    supporting_rows: tuple[dict[str, Any], ...] = ()
    diagnostic_rows: tuple[dict[str, Any], ...] = ()
    asset_kind: str | None = None
    role_source: str | None = None
    identity_confidence: float | None = None
    identity_evidence: tuple[str, ...] = ()
    collision_risk: str | None = None
    role_capabilities: Mapping[str, bool] | None = None
    role_validation_failures: tuple[str, ...] = ()

    @property
    def alertable(self) -> bool:
        return event_alpha_router.route_value_is_alertable(self.final_route_after_quality_gate)

    @property
    def is_high_priority(self) -> bool:
        return (
            self.opportunity_level == "high_priority"
            or self.final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
            or self.final_state_after_quality_gate == event_watchlist.EventWatchlistState.HIGH_PRIORITY.value
        )

    @property
    def is_watchlist(self) -> bool:
        return (
            self.opportunity_level == "watchlist"
            or self.final_state_after_quality_gate == event_watchlist.EventWatchlistState.WATCHLIST.value
        )

    @property
    def is_validated_digest(self) -> bool:
        return (
            self.opportunity_level == "validated_digest"
            or self.final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
        )


@dataclass(frozen=True)
class CanonicalCoreResolution:
    canonical_core_opportunity_id: str | None
    resolution_status: str
    diagnostic_support_for_core_opportunity_id: str | None = None
    warnings: tuple[str, ...] = ()


VISIBLE_CORE_GROUPS = {
    "High-Priority Core Opportunities",
    "Validated Digest Core Opportunities",
    "Watchlist Core Opportunities",
    "Near-Miss Candidates",
    "Quality-Capped / Local-Only Candidates",
}


def aggregate_core_opportunities(rows: Iterable[Any]) -> tuple[CoreOpportunity, ...]:
    """Aggregate compatible rows into operator-facing core opportunities."""
    normalized = [_normalize_row(item) for item in rows]
    normalized = [row for row in normalized if row and _asset_key(row)]

    groups: dict[str, list[dict[str, Any]]] = {}
    diagnostics: list[dict[str, Any]] = []
    for row in normalized:
        if _is_diagnostic_row(row):
            diagnostics.append(row)
            continue
        key = _core_key(row)
        if key:
            groups.setdefault(key, []).append(row)

    diagnostics_by_key: dict[str, list[dict[str, Any]]] = {key: [] for key in groups}
    for row in diagnostics:
        exact = _core_key(row)
        if exact in diagnostics_by_key:
            diagnostics_by_key[exact].append(row)
            continue
        incident_asset = _incident_asset_key(row)
        matches = [key for key, members in groups.items() if members and _incident_asset_key(members[0]) == incident_asset]
        if matches:
            diagnostics_by_key[matches[0]].append(row)

    promoted_by_incident_asset: dict[tuple[str, str], str] = {}
    promoted_by_asset: dict[str, str] = {}
    for key, members in groups.items():
        promoted = [row for row in members if _is_promoted_row(row)]
        if not promoted:
            continue
        incident_asset = _incident_asset_key(promoted[0])
        asset = _asset_key(promoted[0])
        existing = promoted_by_incident_asset.get(incident_asset)
        if existing is None:
            promoted_by_incident_asset[incident_asset] = key
        else:
            existing_primary = sorted(groups.get(existing, []), key=_row_rank, reverse=True)[0]
            current_primary = sorted(promoted, key=_row_rank, reverse=True)[0]
            if _row_rank(current_primary) > _row_rank(existing_primary):
                promoted_by_incident_asset[incident_asset] = key
        existing_asset = promoted_by_asset.get(asset)
        if existing_asset is None:
            promoted_by_asset[asset] = key
        else:
            existing_primary = sorted(groups.get(existing_asset, []), key=_row_rank, reverse=True)[0]
            current_primary = sorted(promoted, key=_row_rank, reverse=True)[0]
            if _row_rank(current_primary) > _row_rank(existing_primary):
                promoted_by_asset[asset] = key

    for key, members in list(groups.items()):
        incident_asset = _incident_asset_key(members[0])
        promoted_key = promoted_by_incident_asset.get(incident_asset) or promoted_by_asset.get(_asset_key(members[0]))
        if not promoted_key or promoted_key == key:
            continue
        if all(_should_attach_to_promoted_core(row) for row in members):
            diagnostics_by_key.setdefault(promoted_key, []).extend(members)
            groups.pop(key, None)

    opportunities: list[CoreOpportunity] = []
    for key, members in groups.items():
        diagnostic_rows = diagnostics_by_key.get(key, [])
        primary = sorted(members, key=_row_rank, reverse=True)[0]
        supporting = tuple(_dedupe_rows([*members, *diagnostic_rows]))
        opportunities.append(_build_core_opportunity(key, primary, supporting, tuple(diagnostic_rows)))

    return tuple(sorted(opportunities, key=lambda item: _opportunity_rank(item), reverse=True))


def core_opportunity_visibility_group(
    opportunity: CoreOpportunity,
    *,
    include_diagnostics: bool = False,
) -> str | None:
    """Return the default operator-visible group for a core opportunity.

    This is presentation-only: it does not route, score, send, or mutate rows.
    """
    if not include_diagnostics and _core_is_diagnostic_only(opportunity):
        return None
    if opportunity.is_high_priority:
        return "High-Priority Core Opportunities"
    if opportunity.is_validated_digest:
        return "Validated Digest Core Opportunities"
    if opportunity.is_watchlist:
        return "Watchlist Core Opportunities"
    if _core_is_near_miss_like(opportunity):
        return "Near-Miss Candidates"
    if not _core_is_diagnostic_only(opportunity):
        return "Quality-Capped / Local-Only Candidates"
    return "Diagnostics / Source-Noise / Controls" if include_diagnostics else None


def core_opportunity_is_visible(
    opportunity: CoreOpportunity,
    *,
    include_diagnostics: bool = False,
) -> bool:
    return core_opportunity_visibility_group(opportunity, include_diagnostics=include_diagnostics) in VISIBLE_CORE_GROUPS


def visible_core_opportunities(
    rows: Iterable[Any],
    *,
    include_diagnostics: bool = False,
) -> tuple[CoreOpportunity, ...]:
    return tuple(
        item
        for item in aggregate_core_opportunities(rows)
        if core_opportunity_is_visible(item, include_diagnostics=include_diagnostics)
    )


def core_opportunity_id_for_row(row: Any) -> str | None:
    normalized = _normalize_row(row)
    explicit = _clean(normalized.get("core_opportunity_id") or normalized.get("aggregated_candidate_id"))
    if explicit:
        return explicit
    key = _core_key(normalized)
    if not key:
        return None
    return _core_id(key)


def resolve_canonical_core_opportunity_id(
    row: Any,
    core_store_rows: Iterable[Any],
) -> CanonicalCoreResolution:
    """Resolve a row against the canonical CoreOpportunity store.

    Visible/operator rows may only use a core id from the store. Diagnostic
    rows can support a canonical core, but they are not themselves canonical.
    """
    normalized = _normalize_row(row)
    if not normalized:
        return CanonicalCoreResolution(None, "no_core", warnings=("empty_row",))
    store = tuple(_core_opportunities_from_rows(core_store_rows))
    if not store:
        fallback = core_opportunity_id_for_row(normalized)
        status = "diagnostic_orphan" if _is_diagnostic_row(normalized) else "orphan"
        warning = "core_store_empty"
        return CanonicalCoreResolution(
            None if _is_diagnostic_row(normalized) else fallback,
            status,
            warnings=(warning,),
        )
    by_id = {item.core_opportunity_id: item for item in store}
    explicit = _clean(normalized.get("core_opportunity_id") or normalized.get("aggregated_candidate_id"))
    diagnostic = _is_diagnostic_row(normalized)
    if explicit and explicit in by_id:
        if diagnostic:
            return CanonicalCoreResolution(
                explicit,
                "diagnostic_support",
                diagnostic_support_for_core_opportunity_id=explicit,
            )
        return CanonicalCoreResolution(explicit, "canonical")
    identifier_support = _matching_core_by_row_identifier(normalized, store)
    if identifier_support is not None:
        warnings = () if not explicit else (f"noncanonical_core_id_replaced:{explicit}",)
        return CanonicalCoreResolution(
            identifier_support.core_opportunity_id,
            "diagnostic_support",
            diagnostic_support_for_core_opportunity_id=identifier_support.core_opportunity_id,
            warnings=warnings,
        )
    support = _matching_core_for_row(normalized, store, diagnostic_only=True)
    if support is not None and diagnostic:
        warnings = () if not explicit else (f"noncanonical_core_id_replaced:{explicit}",)
        return CanonicalCoreResolution(
            support.core_opportunity_id,
            "diagnostic_support",
            diagnostic_support_for_core_opportunity_id=support.core_opportunity_id,
            warnings=warnings,
        )
    match = _matching_core_for_row(normalized, store, diagnostic_only=False)
    if match is not None:
        warnings = () if not explicit or explicit == match.core_opportunity_id else (f"noncanonical_core_id_replaced:{explicit}",)
        return CanonicalCoreResolution(match.core_opportunity_id, "canonical", warnings=warnings)
    if diagnostic:
        return CanonicalCoreResolution(
            None,
            "orphan",
            warnings=(f"diagnostic_core_orphan:{explicit}",) if explicit else ("diagnostic_core_orphan",),
        )
    if explicit and not _asset_key(normalized):
        return CanonicalCoreResolution(
            explicit,
            "orphan",
            warnings=(f"visible_core_missing_store_row:{explicit}", "missing_asset_identity"),
        )
    if not _asset_key(normalized):
        return CanonicalCoreResolution(None, "no_core", warnings=("missing_asset_identity",))
    fallback = explicit or core_opportunity_id_for_row(normalized)
    return CanonicalCoreResolution(
        fallback,
        "orphan",
        warnings=(f"visible_core_missing_store_row:{fallback}",) if fallback else ("visible_core_missing_store_row",),
    )


def row_key_candidates_for_opportunity(opportunity: CoreOpportunity) -> tuple[str, ...]:
    values: list[str] = []
    for row in (opportunity.primary_row, *opportunity.supporting_rows):
        for key in ("key", "alert_key", "event_id", "hypothesis_id", "watchlist_key"):
            value = str(row.get(key) or "").strip()
            if value:
                values.append(value)
    return tuple(dict.fromkeys(values))


def incident_asset_key_for_values(incident_id: object, coin_id: object, symbol: object) -> tuple[str, str]:
    incident = _clean(incident_id) or "unknown_incident"
    asset = _clean(coin_id) or _clean(symbol).upper()
    return incident, asset


def incident_asset_key_for_opportunity(opportunity: CoreOpportunity) -> tuple[str, str]:
    return incident_asset_key_for_values(opportunity.incident_id, opportunity.coin_id, opportunity.symbol)


def asset_key_for_values(coin_id: object, symbol: object) -> str:
    return incident_asset_key_for_values("incident", coin_id, symbol)[1]


def asset_key_for_opportunity(opportunity: CoreOpportunity) -> str:
    return asset_key_for_values(opportunity.coin_id, opportunity.symbol)


def row_is_diagnostic(row: Any) -> bool:
    return _is_diagnostic_row(_normalize_row(row))


def _core_opportunities_from_rows(rows: Iterable[Any]) -> tuple[CoreOpportunity, ...]:
    direct: list[CoreOpportunity] = []
    raw: list[Any] = []
    for item in rows:
        if isinstance(item, CoreOpportunity):
            direct.append(item)
        else:
            raw.append(item)
    return tuple([*direct, *aggregate_core_opportunities(raw)])


def _matching_core_for_row(
    row: Mapping[str, Any],
    store: Iterable[CoreOpportunity],
    *,
    diagnostic_only: bool,
) -> CoreOpportunity | None:
    incident_asset = _incident_asset_key(row)
    asset = _asset_key(row)
    row_role = _normalized_role(_value(row, _components(row), "candidate_role", "relationship_type", "latest_effective_playbook_type", "playbook_type"))
    row_family = _impact_path_family(_primary_impact_path(row) or _value(row, _components(row), "impact_category"))
    candidates: list[tuple[int, CoreOpportunity]] = []
    for item in store:
        if incident_asset == incident_asset_key_for_opportunity(item):
            if diagnostic_only:
                candidates.append((100, item))
                continue
            role_match = row_role in {"", "unknown", item.candidate_role, _normalized_role(item.candidate_role)}
            family_match = row_family in {"", "unknown", _impact_path_family(item.primary_impact_path)} or _impact_path_family(item.primary_impact_path) == row_family
            if role_match and family_match:
                candidates.append((100, item))
            elif family_match:
                candidates.append((80, item))
        elif asset and asset == asset_key_for_opportunity(item):
            if diagnostic_only:
                candidates.append((60, item))
                continue
            family_match = row_family in {"", "unknown", _impact_path_family(item.primary_impact_path)} or _impact_path_family(item.primary_impact_path) == row_family
            if family_match:
                candidates.append((60, item))
    if not candidates:
        return None
    return sorted(candidates, key=lambda pair: (pair[0], _opportunity_rank(pair[1])), reverse=True)[0][1]


def _matching_core_by_row_identifier(
    row: Mapping[str, Any],
    store: Iterable[CoreOpportunity],
) -> CoreOpportunity | None:
    candidates = _row_identifier_candidates(row)
    if not candidates:
        return None
    matches: list[tuple[int, CoreOpportunity]] = []
    for item in store:
        support_ids = _core_support_identifier_candidates(item)
        if not support_ids.intersection(candidates):
            continue
        rank = 100 if _asset_key(row) == asset_key_for_opportunity(item) else 80
        matches.append((rank, item))
    if not matches:
        return None
    return sorted(matches, key=lambda pair: (pair[0], _opportunity_rank(pair[1])), reverse=True)[0][1]


def _row_identifier_candidates(row: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()
    for key in ("row_id", "alert_id", "key", "watchlist_key", "event_id", "hypothesis_id"):
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        out.add(value)
        if value.startswith("ea:"):
            out.add(value[3:])
    return out


def _core_support_identifier_candidates(item: CoreOpportunity) -> set[str]:
    out: set[str] = set()
    rows = (item.primary_row, *item.supporting_rows, *item.diagnostic_rows)
    for row in rows:
        for key in (
            "supporting_row_ids",
            "diagnostic_row_ids",
            "supporting_hypothesis_ids",
            "row_id",
            "alert_id",
            "key",
            "watchlist_key",
            "event_id",
            "hypothesis_id",
        ):
            raw = row.get(key)
            if raw in (None, "", [], {}, ()):
                continue
            if isinstance(raw, str):
                values = [raw]
            elif isinstance(raw, Mapping):
                values = [str(value) for value in raw.values()]
            elif isinstance(raw, Iterable):
                values = [str(value) for value in raw]
            else:
                values = [str(raw)]
            for value in values:
                text = str(value or "").strip()
                if not text:
                    continue
                out.add(text)
                if text.startswith("ea:"):
                    out.add(text[3:])
    return out


def _build_core_opportunity(
    key: str,
    primary: dict[str, Any],
    supporting: tuple[dict[str, Any], ...],
    diagnostics: tuple[dict[str, Any], ...],
) -> CoreOpportunity:
    components = _components(primary)
    symbol = _symbol(primary) or "UNKNOWN"
    coin_id = _coin_id(primary) or "unknown"
    role = _value(primary, components, "candidate_role") or "unknown"
    impact_path = _primary_impact_path(primary) or "unknown"
    level = _value(primary, components, "opportunity_level") or "unknown"
    score = _float(_value(primary, components, "opportunity_score_final"))
    route = _final_route(primary)
    state = _final_state(primary)
    supporting_ids = _collect_values(supporting, ("supporting_hypothesis_ids", "hypothesis_id"))
    categories = _collect_values(supporting, ("supporting_categories", "impact_category"))
    paths = _collect_values(supporting, ("supporting_impact_paths", "primary_impact_path", "impact_path_type", "impact_path_reason"))
    quotes = _collect_values(supporting, ("supporting_evidence_quotes", "evidence_quotes", "main_frame_evidence_quote"))
    source_noise_count = sum(1 for row in diagnostics if _is_source_noise_control(row))
    capped_count = sum(1 for row in supporting if _bool(row.get("state_quality_capped")))
    visible_reason = _visible_reason(primary, route, state, level)
    hidden_reason = _hidden_reason(len(supporting), len(diagnostics), capped_count)
    identity_evidence = _collect_values(supporting, ("identity_evidence", "resolver_identity_evidence"))
    role_failures = _collect_values(supporting, ("role_validation_failures", "role_validation_failure"))
    return CoreOpportunity(
        core_opportunity_id=_explicit_core_id(supporting) or _core_id(key),
        incident_id=_optional(_value(primary, components, "incident_id", "event_cluster_id", "cluster_id")),
        canonical_incident_name=_optional(_value(primary, components, "canonical_incident_name", "incident_canonical_name", "canonical_name")),
        symbol=symbol,
        coin_id=coin_id,
        candidate_role=role,
        primary_impact_path=impact_path,
        opportunity_level=level,
        opportunity_score_final=score,
        final_route_after_quality_gate=route,
        final_state_after_quality_gate=state,
        supporting_hypothesis_ids=supporting_ids,
        supporting_categories=categories,
        supporting_impact_paths=paths,
        supporting_evidence_quotes=quotes,
        diagnostic_row_count=len(diagnostics),
        source_noise_control_count=source_noise_count,
        quality_capped_supporting_rows=capped_count,
        why_opportunity_visible=visible_reason,
        why_other_rows_hidden=hidden_reason,
        primary_row=primary,
        supporting_rows=supporting,
        diagnostic_rows=diagnostics,
        asset_kind=_optional(_value(primary, components, "asset_kind")),
        role_source=_optional(_value(primary, components, "role_source", "asset_role_source")),
        identity_confidence=_float(_value(primary, components, "identity_confidence")),
        identity_evidence=identity_evidence,
        collision_risk=_optional(_value(primary, components, "collision_risk")),
        role_capabilities=_mapping_value(primary, components, "role_capabilities"),
        role_validation_failures=role_failures,
    )


def _normalize_row(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, event_alpha_router.EventAlphaRouteDecision):
        row = _entry_as_row(item.entry)
        row.update({
            "route": item.route.value,
            "alertable": item.alertable,
            "route_reason": item.reason,
            "lane": item.lane.value,
            "requested_route_before_quality_gate": item.requested_route_before_quality_gate,
            "final_route_after_quality_gate": event_alpha_router.final_route_value(item),
            "quality_gate_block_reason": item.quality_gate_block_reason,
            "opportunity_level": item.opportunity_level or row.get("opportunity_level"),
            "opportunity_score_final": item.opportunity_score_final
            if item.opportunity_score_final is not None
            else row.get("opportunity_score_final"),
        })
    elif isinstance(item, event_watchlist.EventWatchlistEntry):
        row = _entry_as_row(item)
    elif isinstance(item, Mapping):
        row = dict(item)
    elif is_dataclass(item):
        row = asdict(item)
    else:
        row = dict(getattr(item, "__dict__", {}) or {})
    if not row:
        return {}
    components = _components(row)
    quality = event_alpha_quality_fields.ensure_quality_fields(row, components=components)
    for key, value in quality.items():
        row.setdefault(key, value)
    if row.get("final_opportunity_level") not in (None, ""):
        row["opportunity_level"] = row.get("final_opportunity_level")
    elif components.get("final_opportunity_level") not in (None, ""):
        row["opportunity_level"] = components.get("final_opportunity_level")
    if row.get("final_opportunity_score") not in (None, ""):
        row["opportunity_score_final"] = row.get("final_opportunity_score")
    elif components.get("final_opportunity_score") not in (None, ""):
        row["opportunity_score_final"] = components.get("final_opportunity_score")
    row.setdefault("validated_symbol", components.get("validated_symbol"))
    row.setdefault("validated_coin_id", components.get("validated_coin_id"))
    row.setdefault("candidate_role", components.get("candidate_role"))
    row.setdefault("impact_path_type", components.get("impact_path_type"))
    row.setdefault("impact_path_reason", components.get("impact_path_reason"))
    row.setdefault("impact_category", components.get("impact_category"))
    row.setdefault("opportunity_level", components.get("opportunity_level"))
    row.setdefault("opportunity_score_final", components.get("opportunity_score_final"))
    row.setdefault("final_state_after_quality_gate", row.get("state"))
    return row


def _mapping_value(row: Mapping[str, Any], components: Mapping[str, Any], key: str) -> Mapping[str, bool] | None:
    value = row.get(key)
    if not isinstance(value, Mapping):
        value = components.get(key)
    if not isinstance(value, Mapping):
        return None
    return {str(k): bool(v) for k, v in value.items()}


def _entry_as_row(entry: event_watchlist.EventWatchlistEntry) -> dict[str, Any]:
    row = asdict(entry)
    row["state"] = event_watchlist.final_state_value(entry)
    row["requested_state_before_quality_gate"] = event_watchlist.requested_state_value(entry)
    row["final_state_after_quality_gate"] = event_watchlist.final_state_value(entry)
    row["state_quality_capped"] = event_watchlist.state_is_quality_capped(entry)
    components = dict(entry.latest_score_components or {})
    for key in event_alpha_quality_fields.REQUIRED_QUALITY_FIELDS:
        value = getattr(entry, key, None)
        if value not in (None, "", [], {}, ()):
            row[key] = value
    for key, value in components.items():
        row.setdefault(key, value)
    return row


def _components(row: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("latest_score_components", "score_components", "_components"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def _core_key(row: Mapping[str, Any]) -> str | None:
    incident, asset = _incident_asset_key(row)
    if not asset:
        return None
    components = _components(row)
    role = _normalized_role(_value(row, components, "candidate_role", "relationship_type", "latest_effective_playbook_type", "playbook_type"))
    family = _impact_path_family(_primary_impact_path(row) or _value(row, components, "impact_category"))
    return "|".join((incident or "unknown_incident", asset, role or "unknown_role", family or "unknown_family"))


def _incident_asset_key(row: Mapping[str, Any]) -> tuple[str, str]:
    components = _components(row)
    incident = _clean(_value(row, components, "incident_id", "event_cluster_id", "cluster_id", "event_id")) or "unknown_incident"
    return incident_asset_key_for_values(incident, _coin_id(row), _symbol(row))


def _asset_key(row: Mapping[str, Any]) -> str:
    return incident_asset_key_for_values("incident", _coin_id(row), _symbol(row))[1]


def _symbol(row: Mapping[str, Any]) -> str:
    components = _components(row)
    return _clean(_value(row, components, "validated_symbol", "symbol", "asset_symbol")).upper()


def _coin_id(row: Mapping[str, Any]) -> str:
    components = _components(row)
    return _clean(_value(row, components, "validated_coin_id", "coin_id", "asset_coin_id"))


def _primary_impact_path(row: Mapping[str, Any]) -> str:
    components = _components(row)
    return _clean(_value(row, components, "primary_impact_path", "impact_path_type", "impact_path_reason", "impact_category"))


def _normalized_role(value: object) -> str:
    text = _clean(value)
    if text in {
        event_playbooks.EventPlaybookType.PROXY_FADE.value,
        event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
    }:
        return "proxy"
    return text


def _impact_path_family(value: object) -> str:
    text = _clean(value).replace("-", "_")
    compact = text.replace("_", " ")
    if any(term in compact for term in ("proxy", "venue", "preipo", "pre ipo", "tokenized", "value capture", "exposure", "rwa")):
        return "proxy_value_capture"
    if any(term in compact for term in ("exploit", "security")):
        return "security"
    if any(term in compact for term in ("listing", "liquidity")):
        return "listing_liquidity"
    if any(term in compact for term in ("investment", "valuation", "stake", "acquisition")):
        return "strategic_investment"
    if any(term in compact for term in ("unlock", "supply")):
        return "unlock_supply"
    if any(term in compact for term in ("fan", "sports", "world cup")):
        return "fan_attention"
    return text or "unknown"


def _is_diagnostic_row(row: Mapping[str, Any]) -> bool:
    components = _components(row)
    role = _clean(_value(row, components, "candidate_role", "llm_asset_role"))
    playbook = _clean(_value(row, components, "latest_effective_playbook_type", "latest_playbook_type", "playbook_type"))
    path = _clean(_value(row, components, "impact_path_type", "impact_path_reason"))
    text = " ".join(str(value or "") for value in (
        role,
        playbook,
        path,
        row.get("warnings"),
        components.get("warnings"),
        row.get("rejection_reasons"),
        components.get("rejection_reasons"),
    )).casefold()
    if _is_source_noise_control(row):
        return True
    return any(term in text for term in (
        "source_noise",
        "ticker_word_collision",
        "ticker_collision",
        "word_collision",
        "publisher_suffix_false_positive",
    ))


def _is_source_noise_control(row: Mapping[str, Any]) -> bool:
    components = _components(row)
    playbook = _clean(_value(row, components, "latest_effective_playbook_type", "latest_playbook_type", "playbook_type"))
    role = _clean(_value(row, components, "candidate_role", "llm_asset_role"))
    return playbook in {
        event_playbooks.EventPlaybookType.SOURCE_NOISE_CONTROL.value,
        event_playbooks.EventPlaybookType.AMBIGUOUS_CONTROL.value,
    } or role in {"source_noise", "ticker_word_collision"}


def _core_is_diagnostic_only(opportunity: CoreOpportunity) -> bool:
    primary = opportunity.primary_row
    if _is_diagnostic_row(primary):
        return True
    text = " ".join(str(value or "") for value in (
        opportunity.candidate_role,
        opportunity.primary_impact_path,
        opportunity.opportunity_level,
        opportunity.final_route_after_quality_gate,
        primary.get("warnings"),
        primary.get("rejection_reasons"),
    )).casefold()
    return any(term in text for term in (
        "source_noise",
        "ticker_word_collision",
        "ticker_collision",
        "word_collision",
        "generic_cooccurrence_only",
    ))


def _core_is_near_miss_like(opportunity: CoreOpportunity) -> bool:
    if opportunity.alertable or opportunity.is_high_priority or opportunity.is_watchlist or opportunity.is_validated_digest:
        return False
    score = opportunity.opportunity_score_final
    level = str(opportunity.opportunity_level or "").casefold()
    if level == "exploratory":
        return True
    if score >= 50:
        return True
    text = " ".join(str(value or "") for value in (
        opportunity.primary_row.get("why_not_watchlist"),
        opportunity.primary_row.get("why_local_only"),
        opportunity.primary_row.get("missing_requirements"),
        opportunity.primary_row.get("upgrade_requirements"),
    )).casefold()
    return any(term in text for term in ("market", "evidence", "impact_path", "source", "refresh"))


def _is_promoted_row(row: Mapping[str, Any]) -> bool:
    route = _final_route(row)
    state = _final_state(row)
    level = _clean(row.get("opportunity_level"))
    return (
        event_alpha_router.route_value_is_alertable(route)
        or route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
        or state in {
            event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            event_watchlist.EventWatchlistState.WATCHLIST.value,
            event_watchlist.EventWatchlistState.RADAR.value,
        }
        or level in {"high_priority", "watchlist", "validated_digest"}
    ) and not _bool(row.get("state_quality_capped"))


def _should_attach_to_promoted_core(row: Mapping[str, Any]) -> bool:
    if _is_diagnostic_row(row):
        return True
    route = _final_route(row)
    state = _final_state(row)
    level = _clean(row.get("opportunity_level"))
    components = _components(row)
    role = _clean(_value(row, components, "candidate_role"))
    path = _clean(_value(row, components, "impact_path_type", "impact_path_reason"))
    if _bool(row.get("state_quality_capped")):
        return True
    if level in {"local_only", "exploratory"}:
        return True
    if route in {
        "",
        event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value,
    }:
        return True
    if state in {
        "",
        event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value,
        event_watchlist.EventWatchlistState.RAW_EVIDENCE.value,
        event_watchlist.EventWatchlistState.HYPOTHESIS.value,
    }:
        return True
    return role in {"unknown_with_reason", "generic_mention"} or path in {"insufficient_data", "generic_cooccurrence_only"}


def _row_rank(row: Mapping[str, Any]) -> tuple[int, int, int, float, int]:
    route = _final_route(row)
    state = _final_state(row)
    level = _clean(row.get("opportunity_level"))
    canonical_rank = 2 if _clean(row.get("row_type")) == "event_core_opportunity" else 0
    route_rank = {
        event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH.value: 6,
        event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value: 5,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value: 4,
        event_alpha_router.EventAlphaRoute.LOCAL_REPORT.value: 2,
        event_alpha_router.EventAlphaRoute.STORE_ONLY.value: 1,
    }.get(route, 0)
    level_rank = {
        "high_priority": 5,
        "watchlist": 4,
        "validated_digest": 3,
        "exploratory": 2,
        "local_only": 1,
    }.get(level, 0)
    state_rank = {
        event_watchlist.EventWatchlistState.TRIGGERED_FADE.value: 6,
        event_watchlist.EventWatchlistState.HIGH_PRIORITY.value: 5,
        event_watchlist.EventWatchlistState.WATCHLIST.value: 4,
        event_watchlist.EventWatchlistState.RADAR.value: 3,
        event_watchlist.EventWatchlistState.HYPOTHESIS.value: 2,
        event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value: 1,
    }.get(state, 0)
    return (canonical_rank, route_rank, level_rank, _float(row.get("opportunity_score_final") or row.get("latest_score") or row.get("hypothesis_score")), state_rank)


def _opportunity_rank(item: CoreOpportunity) -> tuple[int, int, float, str]:
    route_rank = 3 if item.is_high_priority else 2 if item.is_watchlist or item.is_validated_digest else 1 if item.alertable else 0
    return (route_rank, int(item.diagnostic_row_count == 0), item.opportunity_score_final, item.symbol)


def _final_route(row: Mapping[str, Any]) -> str:
    value = row.get("final_route_after_quality_gate") or row.get("route") or ""
    return str(getattr(value, "value", value) or "")


def _final_state(row: Mapping[str, Any]) -> str:
    value = row.get("final_state_after_quality_gate") or row.get("state") or ""
    return str(getattr(value, "value", value) or "")


def _visible_reason(row: Mapping[str, Any], route: str, state: str, level: str) -> str:
    if route == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value or level == "high_priority":
        return "highest quality-gated high-priority row for this incident/asset"
    if route == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value or level == "validated_digest":
        return "highest quality-gated digest row for this incident/asset"
    if state in {event_watchlist.EventWatchlistState.WATCHLIST.value, event_watchlist.EventWatchlistState.RADAR.value}:
        return "highest lifecycle row for this incident/asset"
    if _bool(row.get("state_quality_capped")):
        return "quality-capped local row retained for diagnostics"
    return "highest non-control row for this incident/asset"


def _hidden_reason(total_rows: int, diagnostic_rows: int, capped_rows: int) -> str:
    reasons: list[str] = []
    support_count = max(0, total_rows - 1)
    if support_count:
        reasons.append(f"{support_count} compatible supporting row(s) collapsed")
    if diagnostic_rows:
        reasons.append(f"{diagnostic_rows} source-noise/control diagnostic row(s) hidden")
    if capped_rows:
        reasons.append(f"{capped_rows} quality-capped supporting row(s) kept as diagnostics")
    return "; ".join(reasons) or "no hidden supporting rows"


def _collect_values(rows: Iterable[Mapping[str, Any]], keys: tuple[str, ...]) -> tuple[str, ...]:
    values: list[str] = []
    for row in rows:
        components = _components(row)
        for key in keys:
            raw = row.get(key)
            if raw is None:
                raw = components.get(key)
            if isinstance(raw, str):
                if raw:
                    values.append(raw)
            elif isinstance(raw, Mapping):
                label = raw.get("symbol") or raw.get("coin_id") or raw.get("name")
                if label:
                    values.append(str(label))
            elif isinstance(raw, Iterable):
                for item in raw:
                    if isinstance(item, Mapping):
                        label = item.get("symbol") or item.get("coin_id") or item.get("name")
                        if label:
                            values.append(str(label))
                    elif str(item or ""):
                        values.append(str(item))
    return tuple(dict.fromkeys(values))


def _dedupe_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        identity = "|".join(str(row.get(key) or "") for key in ("hypothesis_id", "key", "alert_key", "event_id", "route", "state"))
        if identity in seen:
            continue
        seen.add(identity)
        out.append(row)
    return out


def _core_id(key: str) -> str:
    return "core_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def _explicit_core_id(rows: Iterable[Mapping[str, Any]]) -> str | None:
    for row in rows:
        value = _clean(row.get("core_opportunity_id") or row.get("aggregated_candidate_id"))
        if value:
            return value
    return None


def _value(row: Mapping[str, Any], components: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}, ()):
            return value
        value = components.get(key)
        if value not in (None, "", [], {}, ()):
            return value
    return None


def _clean(value: object) -> str:
    return str(value or "").strip()


def _optional(value: object) -> str | None:
    clean = _clean(value)
    return clean or None


def _float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y"}
    return bool(value)
