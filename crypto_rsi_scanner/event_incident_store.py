"""Profile-scoped canonical incident artifacts for Event Alpha research.

The incident store links raw event evidence, claim semantics, impact
hypotheses, watchlist rows, and market/causal context. It is a local research
artifact only; it cannot send alerts, open paper trades, write normal RSI
signal rows, or create event-fade triggers.
"""

from __future__ import annotations

import json
from collections.abc import Iterable as IterableABC
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from . import event_claim_semantics, event_incident_graph
from .event_models import EventDiscoveryResult, RawDiscoveredEvent


INCIDENT_STORE_SCHEMA_VERSION = "event_incident_store_v1"


@dataclass(frozen=True)
class EventIncidentStoreConfig:
    path: Path


@dataclass(frozen=True)
class EventIncidentStoreWriteResult:
    path: Path
    attempted: bool
    success: bool
    rows_written: int = 0
    block_reason: str | None = None


@dataclass(frozen=True)
class EventIncidentStoreReadResult:
    path: Path
    rows_read: int
    rows: list[dict[str, Any]]
    total_rows_read: int = 0
    latest_run_id: str | None = None
    latest_run_rows_available: int = 0
    historical_rows_available: int = 0
    legacy_rows_available: int = 0
    filters: dict[str, Any] = field(default_factory=dict)


def build_incident_rows(
    discovery_result: EventDiscoveryResult,
    *,
    hypotheses: Iterable[object] = (),
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    now: datetime | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
) -> list[dict[str, Any]]:
    """Build serializable incident rows from a discovery result and links."""
    observed = _as_utc(now or datetime.now(timezone.utc)).isoformat()
    raw_by_id = {raw.raw_id: raw for raw in discovery_result.raw_events}
    incidents = event_incident_graph.build_incidents(discovery_result.normalized_events, raw_by_id)
    hypotheses_by_incident = _hypotheses_by_incident(hypotheses)
    watchlist_by_incident = _watchlist_by_incident(watchlist_rows)
    rows = []
    for incident in incidents:
        matching_hypotheses = hypotheses_by_incident.get(incident.incident_id, [])
        matching_watchlist = watchlist_by_incident.get(incident.incident_id, [])
        rows.append(_row_from_incident(
            incident,
            raw_by_id=raw_by_id,
            observed_at=observed,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
            hypotheses=matching_hypotheses,
            watchlist_rows=matching_watchlist,
        ))
    return rows


def write_incidents(
    discovery_result: EventDiscoveryResult,
    *,
    cfg: EventIncidentStoreConfig,
    hypotheses: Iterable[object] = (),
    watchlist_rows: Iterable[Mapping[str, Any] | object] = (),
    now: datetime | None = None,
    run_id: str | None = None,
    profile: str | None = None,
    run_mode: str | None = None,
    artifact_namespace: str | None = None,
) -> EventIncidentStoreWriteResult:
    """Append canonical incident rows to a local JSONL artifact."""
    path = cfg.path.expanduser()
    try:
        rows = build_incident_rows(
            discovery_result,
            hypotheses=hypotheses,
            watchlist_rows=watchlist_rows,
            now=now,
            run_id=run_id,
            profile=profile,
            run_mode=run_mode,
            artifact_namespace=artifact_namespace,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(_json_ready(row), sort_keys=True, separators=(",", ":")))
                fh.write("\n")
        return EventIncidentStoreWriteResult(path=path, attempted=True, success=True, rows_written=len(rows))
    except Exception as exc:  # noqa: BLE001 - artifact writes must fail soft.
        return EventIncidentStoreWriteResult(
            path=path,
            attempted=True,
            success=False,
            rows_written=0,
            block_reason=f"{type(exc).__name__}: {exc}",
        )


def load_incidents(
    path: str | Path,
    *,
    limit: int | None = None,
    latest_run: bool = False,
    run_id: str | None = None,
    include_legacy: bool = True,
) -> EventIncidentStoreReadResult:
    """Load stored incidents newest-first, tolerating malformed legacy rows."""
    p = Path(path).expanduser()
    all_rows = [
        row for row in _read_jsonl(p)
        if row.get("row_type") == "event_incident"
    ]
    all_rows.sort(key=lambda row: str(row.get("last_updated_at") or row.get("observed_at") or ""), reverse=True)
    latest_id = _latest_run_id(all_rows)
    latest_count = sum(1 for row in all_rows if _row_run_id(row) == latest_id) if latest_id else 0
    legacy_count = sum(1 for row in all_rows if _is_legacy_row(row))
    rows = _filter_rows(
        all_rows,
        latest_run=latest_run,
        latest_run_id=latest_id,
        run_id=run_id,
        include_legacy=include_legacy,
    )
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return EventIncidentStoreReadResult(
        path=p,
        rows_read=len(rows),
        rows=rows,
        total_rows_read=len(all_rows),
        latest_run_id=latest_id,
        latest_run_rows_available=latest_count,
        historical_rows_available=max(0, len(all_rows) - latest_count),
        legacy_rows_available=legacy_count,
        filters={
            "latest_run": bool(latest_run),
            "run_id": run_id,
            "include_legacy": bool(include_legacy),
            "limit": limit,
        },
    )


def format_incidents_report(result: EventIncidentStoreReadResult) -> str:
    """Return an operator-readable incident artifact report."""
    rows = [
        "=" * 76,
        "EVENT INCIDENTS REPORT (research artifact only)",
        "=" * 76,
        f"path: {result.path}",
        f"rows_read: {result.rows_read}",
        f"total_rows_available: {result.total_rows_read or result.rows_read}",
        f"latest_run_id: {result.latest_run_id or 'unknown'}",
        f"latest_run_rows_available: {result.latest_run_rows_available}",
        f"historical_rows_available: {result.historical_rows_available}",
        f"legacy_rows_available: {result.legacy_rows_available}",
        "filters: " + _format_filter_summary(result.filters),
    ]
    if not result.rows:
        rows.extend(["", "No stored incidents matched the current report filters."])
        return "\n".join(rows)

    rows.append("event_archetypes: " + _format_counts(_counts(result.rows, "event_archetype")))
    rows.append("cause_statuses: " + _format_counts(_counts(result.rows, "current_cause_status")))
    rows.append("primary_subjects: " + _format_counts(_counts(result.rows, "primary_subject")))
    rows.append("asset_roles: " + _format_counts(_asset_role_counts(result.rows)))
    rows.append(f"conflicting_claim_incidents: {sum(1 for row in result.rows if row.get('conflicting_claims'))}")
    rows.append(f"absence_of_validated_catalyst_claims: {_absence_claim_count(result.rows)}")
    rows.append(f"multiple_source_updates: {sum(1 for row in result.rows if int(row.get('source_update_count') or 0) > 1)}")
    rows.append(f"linked_to_hypotheses: {sum(1 for row in result.rows if row.get('linked_hypothesis_ids'))}")
    rows.append(f"linked_to_watchlist: {sum(1 for row in result.rows if row.get('linked_watchlist_keys'))}")
    rows.append(f"incident_linked_hypotheses_count: {sum(len(row.get('linked_hypothesis_ids') or ()) for row in result.rows)}")
    rows.append(f"incident_linked_watchlist_count: {sum(len(row.get('linked_watchlist_keys') or ()) for row in result.rows)}")
    rows.append("material_update_reasons: " + _format_counts(_material_reason_counts(result.rows)))
    rows.append(
        "market_reaction_unknown_cause: "
        + str(sum(
            1 for row in result.rows
            if (row.get("market_reaction_observed") or row.get("market_reaction_confirmed"))
            and row.get("current_cause_status") in {"unknown", "ruled_out"}
        ))
    )
    rows.append(
        "confirmed_cause_missing_market_data: "
        + str(sum(
            1 for row in result.rows
            if row.get("current_cause_status") == "confirmed" and not row.get("market_context_source")
        ))
    )
    rows.append("")
    rows.append("Notable incidents:")
    for row in result.rows[:25]:
        rows.extend(_incident_lines(row))
    rows.append("")
    rows.append("No sends, trades, paper rows, normal RSI rows, or event-fade state were changed.")
    return "\n".join(rows).rstrip()


def _row_from_incident(
    incident: event_incident_graph.CanonicalIncident,
    *,
    raw_by_id: Mapping[str, RawDiscoveredEvent],
    observed_at: str,
    run_id: str | None,
    profile: str | None,
    run_mode: str | None,
    artifact_namespace: str | None,
    hypotheses: Iterable[object],
    watchlist_rows: Iterable[Mapping[str, Any] | object],
) -> dict[str, Any]:
    h_rows = [_object_row(item) for item in hypotheses]
    w_rows = [_object_row(item) for item in watchlist_rows]
    linked_assets = _linked_assets(h_rows, w_rows)
    market = _incident_market_context(h_rows, w_rows, incident=incident, raw_by_id=raw_by_id)
    claim_history = [_claim_summary(claim) for claim in incident.claim_history[:12]]
    source_urls = tuple(sorted({raw_by_id[raw_id].source_url for raw_id in incident.raw_ids if raw_id in raw_by_id and raw_by_id[raw_id].source_url}))
    current_polarities = tuple(dict.fromkeys(
        str(claim.polarity) for claim in incident.claim_history if str(claim.polarity)
    ))
    row = {
        "schema_version": INCIDENT_STORE_SCHEMA_VERSION,
        "row_type": "event_incident",
        "observed_at": observed_at,
        "run_id": run_id,
        "profile": profile or "default",
        "run_mode": run_mode,
        "artifact_namespace": artifact_namespace,
        "incident_id": incident.incident_id,
        "canonical_name": incident.canonical_name,
        "event_archetype": incident.event_archetype,
        "primary_subject": incident.primary_subject,
        "affected_ecosystem": incident.affected_ecosystem,
        "external_entities": _unique(_flatten_values(h_rows, "external_entities", fallback="external_asset")),
        "crypto_entities": _unique(_crypto_entities(h_rows, w_rows)),
        "first_seen_at": _iso(incident.first_seen_at),
        "last_updated_at": _iso(incident.last_updated_at),
        "current_cause_status": incident.current_cause_status,
        "current_claim_polarities": current_polarities,
        "claim_history": claim_history,
        "conflicting_claims": tuple(incident.conflicting_claims),
        "source_raw_ids": tuple(incident.raw_ids),
        "source_event_ids": tuple(incident.event_ids),
        "source_urls": source_urls[:12],
        "source_domains": tuple(incident.independent_source_domains),
        "independent_source_count": len(incident.independent_source_domains),
        "source_update_count": len(incident.raw_ids),
        "linked_hypothesis_ids": _unique(row.get("hypothesis_id") for row in h_rows),
        "linked_watchlist_keys": _unique(row.get("key") for row in w_rows),
        "linked_assets": linked_assets,
        "asset_roles": _asset_roles(linked_assets),
        "material_update_reasons": _unique(_flatten_values(w_rows, "material_change_reasons")),
        "market_reaction_observed": market["market_reaction_observed"],
        "market_reaction_confirmed": market["market_reaction_confirmed"],
        "market_reaction_level": market["market_reaction_level"],
        "causal_mechanism_confirmed": market["causal_mechanism_confirmed"],
        "market_context_source": market["market_context_source"],
        "market_context_asset": market["market_context_asset"],
        "market_context_age": market["market_context_age"],
        "incident_confidence": _incident_confidence(incident, h_rows, market),
        "warnings": tuple(dict.fromkeys([*incident.warnings, *_incident_warnings(incident, market)])),
    }
    return row


def _hypotheses_by_incident(hypotheses: Iterable[object]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {}
    for item in hypotheses:
        incident_id = _value(_object_row(item), "incident_id")
        if incident_id:
            out.setdefault(incident_id, []).append(item)
    return out


def _watchlist_by_incident(watchlist_rows: Iterable[Mapping[str, Any] | object]) -> dict[str, list[Mapping[str, Any] | object]]:
    out: dict[str, list[Mapping[str, Any] | object]] = {}
    for item in watchlist_rows:
        row = _object_row(item)
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        incident_id = _value(row, "incident_id") or _value(components, "incident_id")
        if incident_id:
            out.setdefault(incident_id, []).append(item)
    return out


def _linked_assets(h_rows: list[dict[str, Any]], w_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    assets: list[dict[str, Any]] = []
    for row in h_rows:
        role = _value(row, "candidate_role")
        validated_asset = row.get("validated_asset") if isinstance(row.get("validated_asset"), Mapping) else {}
        symbol = _value(row, "validated_symbol") or _value(validated_asset, "symbol")
        coin_id = _value(row, "validated_coin_id") or _value(validated_asset, "coin_id")
        if not symbol:
            symbols = row.get("candidate_symbols") or ()
            symbol = str(symbols[0]).upper() if symbols else ""
        if not coin_id:
            coin_ids = row.get("candidate_coin_ids") or ()
            coin_id = str(coin_ids[0]) if coin_ids else ""
        if symbol or coin_id:
            assets.append({
                "symbol": symbol,
                "coin_id": coin_id,
                "role": role or "unknown",
                "role_confidence": row.get("role_confidence"),
                "source": "hypothesis",
            })
    for row in w_rows:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        symbol = _value(row, "symbol") or _value(components, "validated_symbol")
        coin_id = _value(row, "coin_id") or _value(components, "validated_coin_id")
        role = _value(row, "candidate_role") or _value(components, "candidate_role")
        if symbol or coin_id:
            assets.append({
                "symbol": symbol,
                "coin_id": coin_id,
                "role": role or "unknown",
                "role_confidence": row.get("role_confidence") or components.get("role_confidence"),
                "source": "watchlist",
            })
    return tuple(_unique_dicts(assets, keys=("symbol", "coin_id", "role")))


def _asset_roles(linked_assets: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "symbol": asset.get("symbol"),
            "coin_id": asset.get("coin_id"),
            "role": asset.get("role"),
            "confidence": asset.get("role_confidence"),
        }
        for asset in linked_assets
    )


def _material_reason_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for reason in row.get("material_update_reasons") or ():
            key = str(reason or "").strip()
            if key:
                counts[key] = counts.get(key, 0) + 1
    return counts


def _incident_market_context(
    h_rows: list[dict[str, Any]],
    w_rows: list[dict[str, Any]],
    *,
    incident: event_incident_graph.CanonicalIncident | None = None,
    raw_by_id: Mapping[str, RawDiscoveredEvent] | None = None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for row in [*h_rows, *w_rows]:
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        merged = {**dict(components), **row}
        if merged.get("market_reaction_confirmed") is not None or merged.get("market_context_source"):
            candidates.append(merged)
    if incident is not None and raw_by_id is not None:
        for raw_id in incident.raw_ids:
            raw = raw_by_id.get(raw_id)
            payload = raw.raw_json if raw is not None and isinstance(raw.raw_json, Mapping) else {}
            market = payload.get("market") if isinstance(payload.get("market"), Mapping) else {}
            anomaly = payload.get("anomaly") if isinstance(payload.get("anomaly"), Mapping) else {}
            if not market and not anomaly:
                continue
            candidates.append({
                "market_reaction_confirmed": False,
                "causal_mechanism_confirmed": False,
                "market_context_source": "raw_market_anomaly_snapshot" if anomaly else "raw_market_snapshot",
                "market_context_asset": market.get("symbol") or market.get("coin_id") or market.get("id"),
                "market_confirmation_level": "observed",
                "market_confirmation_score": anomaly.get("score") or market.get("anomaly_score") or 1.0,
            })
    if not candidates:
        return {
            "market_reaction_observed": False,
            "market_reaction_confirmed": False,
            "market_reaction_level": "insufficient_data",
            "causal_mechanism_confirmed": False,
            "market_context_source": None,
            "market_context_asset": None,
            "market_context_age": None,
        }
    best = sorted(candidates, key=lambda row: _float(row.get("market_confirmation_score")), reverse=True)[0]
    reaction_observed = any(
        bool(row.get("market_reaction_confirmed"))
        or bool(row.get("market_context_source"))
        or _float(row.get("market_confirmation_score")) > 0
        or str(row.get("market_confirmation_level") or "").casefold() in {"weak", "moderate", "strong"}
        for row in candidates
    )
    return {
        "market_reaction_observed": reaction_observed,
        "market_reaction_confirmed": any(bool(row.get("market_reaction_confirmed")) for row in candidates),
        "market_reaction_level": _value(best, "market_confirmation_level") or "unknown",
        "causal_mechanism_confirmed": any(bool(row.get("causal_mechanism_confirmed")) for row in candidates),
        "market_context_source": _value(best, "market_context_source"),
        "market_context_asset": _value(best, "validated_symbol") or _value(best, "symbol") or _value(best, "coin_id"),
        "market_context_age": best.get("market_context_age_seconds"),
    }


def _incident_confidence(
    incident: event_incident_graph.CanonicalIncident,
    h_rows: list[dict[str, Any]],
    market: Mapping[str, Any],
) -> float:
    score = 35.0 + len(incident.raw_ids) * 10.0 + len(incident.independent_source_domains) * 18.0
    if incident.current_cause_status == event_claim_semantics.CauseStatus.CONFIRMED.value:
        score += 12.0
    elif incident.current_cause_status == event_claim_semantics.CauseStatus.SUSPECTED.value:
        score -= 5.0
    elif incident.current_cause_status == event_claim_semantics.CauseStatus.RULED_OUT.value:
        score -= 8.0
    if market.get("market_reaction_confirmed"):
        score += 5.0
    if market.get("causal_mechanism_confirmed"):
        score += 10.0
    if any(row.get("conflicting_claims") for row in h_rows) or incident.conflicting_claims:
        score -= 10.0
    return round(max(0.0, min(100.0, score)), 2)


def _incident_warnings(
    incident: event_incident_graph.CanonicalIncident,
    market: Mapping[str, Any],
) -> tuple[str, ...]:
    warnings: list[str] = []
    if incident.conflicting_claims:
        warnings.append("conflicting_claims_present")
    if market.get("market_reaction_confirmed") and incident.current_cause_status in {"unknown", "ruled_out"}:
        warnings.append("market_reaction_without_confirmed_cause")
    if incident.current_cause_status == "confirmed" and not market.get("market_context_source"):
        warnings.append("confirmed_cause_missing_market_context")
    return tuple(warnings)


def _claim_summary(claim: event_claim_semantics.EventClaim) -> dict[str, Any]:
    return {
        "claim_type": claim.claim_type,
        "subject": claim.subject,
        "predicate": claim.predicate,
        "object": claim.object,
        "polarity": claim.polarity,
        "cause_status": claim.cause_status,
        "confidence": claim.confidence,
        "evidence_quote": claim.evidence_quote,
    }


def _incident_lines(row: Mapping[str, Any]) -> list[str]:
    assets = row.get("linked_assets") or []
    asset_text = ", ".join(
        f"{asset.get('symbol') or asset.get('coin_id') or 'asset'}:{asset.get('role') or 'unknown'}"
        for asset in list(assets)[:4]
        if isinstance(asset, Mapping)
    ) or "none"
    lines = [
        (
            f"- {row.get('incident_id')}: {row.get('canonical_name')} "
            f"archetype={row.get('event_archetype')} cause={row.get('current_cause_status')} "
            f"sources={row.get('source_update_count')}/{row.get('independent_source_count')} "
            f"confidence={row.get('incident_confidence')}"
        ),
        f"  assets: {asset_text}",
        "  material_update_reasons: "
        + (", ".join(str(item) for item in row.get("material_update_reasons") or ()) or "none"),
        (
            "  market_vs_cause: "
            f"reaction_observed={str(bool(row.get('market_reaction_observed') or row.get('market_reaction_confirmed'))).lower()} "
            f"reaction_confirmed={str(bool(row.get('market_reaction_confirmed'))).lower()} "
            f"level={row.get('market_reaction_level') or 'unknown'} "
            f"causal={str(bool(row.get('causal_mechanism_confirmed'))).lower()} "
            f"source={row.get('market_context_source') or 'none'}"
        ),
    ]
    if row.get("conflicting_claims"):
        lines.append("  conflicting_claims: " + ", ".join(str(item) for item in row.get("conflicting_claims") or ()))
    if row.get("warnings"):
        lines.append("  warnings: " + ", ".join(str(item) for item in row.get("warnings") or ()))
    return lines


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, Mapping):
                    rows.append(dict(value))
    except OSError:
        return []
    return rows


def _filter_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    latest_run: bool,
    latest_run_id: str | None,
    run_id: str | None,
    include_legacy: bool,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        if not include_legacy and _is_legacy_row(data):
            continue
        if run_id and _row_run_id(data) != run_id:
            continue
        if latest_run and latest_run_id and _row_run_id(data) != latest_run_id:
            continue
        out.append(data)
    return out


def _latest_run_id(rows: Iterable[Mapping[str, Any]]) -> str | None:
    for row in rows:
        run_id = _row_run_id(row)
        if run_id:
            return run_id
    return None


def _row_run_id(row: Mapping[str, Any]) -> str | None:
    value = row.get("run_id")
    return str(value) if value not in (None, "") else None


def _is_legacy_row(row: Mapping[str, Any]) -> bool:
    return not str(row.get("schema_version") or "").startswith("event_incident_store_")


def _format_filter_summary(filters: Mapping[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(filters.items())) or "none"


def _counts(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _asset_role_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for asset in row.get("linked_assets") or ():
            if not isinstance(asset, Mapping):
                continue
            role = str(asset.get("role") or "unknown")
            counts[role] = counts.get(role, 0) + 1
    return counts


def _absence_claim_count(rows: Iterable[Mapping[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        for claim in row.get("claim_history") or ()
        if isinstance(claim, Mapping)
        and str(claim.get("claim_type") or "") == "absence_of_validated_catalyst"
    )


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _object_row(item: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(item, Mapping):
        return dict(item)
    data = dict(getattr(item, "__dict__", {}) or {})
    if hasattr(item, "latest_score_components"):
        data["latest_score_components"] = dict(getattr(item, "latest_score_components", {}) or {})
    return data


def _flatten_values(rows: Iterable[Mapping[str, Any]], key: str, *, fallback: str | None = None) -> list[str]:
    values: list[str] = []
    for row in rows:
        raw = row.get(key)
        if raw in (None, "", [], ()):
            raw = row.get(fallback) if fallback else None
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Mapping):
            text = raw.get("name") or raw.get("symbol") or raw.get("coin_id")
            if text not in (None, ""):
                values.append(str(text))
        elif isinstance(raw, IterableABC):
            for item in raw:
                if isinstance(item, Mapping):
                    text = item.get("name") or item.get("symbol") or item.get("coin_id")
                else:
                    text = item
                if text not in (None, ""):
                    values.append(str(text))
    return values


def _crypto_entities(h_rows: list[dict[str, Any]], w_rows: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for row in [*h_rows, *w_rows]:
        values.extend(_flatten_values((row,), "candidate_symbols"))
        for key in ("validated_symbol", "symbol", "coin_id", "validated_coin_id"):
            value = row.get(key)
            if value not in (None, ""):
                values.append(str(value))
        components = row.get("latest_score_components") if isinstance(row.get("latest_score_components"), Mapping) else {}
        for key in ("validated_symbol", "symbol", "coin_id", "validated_coin_id"):
            value = components.get(key)
            if value not in (None, ""):
                values.append(str(value))
    return values


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    out: list[str] = []
    for value in values:
        if value in (None, "", [], {}):
            continue
        text = str(value)
        if text not in out:
            out.append(text)
    return tuple(out)


def _unique_dicts(rows: Iterable[Mapping[str, Any]], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = tuple(str(row.get(part) or "") for part in keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    return out


def _value(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    return str(value).strip() if value not in (None, "", [], {}) else ""


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _iso(value: object) -> str | None:
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(value) if value not in (None, "") else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(child) for child in value]
    return value
