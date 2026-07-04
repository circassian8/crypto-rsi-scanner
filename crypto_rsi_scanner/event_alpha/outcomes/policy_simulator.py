"""Offline policy-threshold simulation for Event Alpha quality artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
import crypto_rsi_scanner.event_alpha.outcomes.quality_fields as event_alpha_quality_fields
import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

_SIMULATOR_EXCLUDED_CLASSIFICATIONS = {
    event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT,
    event_alpha_alert_store.SNAPSHOT_STALE_PRE_QUALITY_GATE,
}


@dataclass(frozen=True)
class EventAlphaPolicyScenario:
    name: str
    opportunity_threshold: float
    require_market_confirmation: bool
    require_impact_path_validated: bool
    allow_weak_macro_with_market: bool
    evidence_quality_minimum: float


@dataclass(frozen=True)
class EventAlphaPolicySimulationResult:
    profile: str | None
    baseline_alertable: tuple[str, ...]
    scenarios: tuple[dict[str, Any], ...]
    legacy_conflicts_excluded: int = 0


DEFAULT_SCENARIOS: tuple[EventAlphaPolicyScenario, ...] = tuple(
    [
        EventAlphaPolicyScenario(
            name="current",
            opportunity_threshold=65.0,
            require_market_confirmation=False,
            require_impact_path_validated=False,
            allow_weak_macro_with_market=False,
            evidence_quality_minimum=60.0,
        ),
        EventAlphaPolicyScenario(
            name="lower_opportunity_threshold",
            opportunity_threshold=55.0,
            require_market_confirmation=False,
            require_impact_path_validated=False,
            allow_weak_macro_with_market=False,
            evidence_quality_minimum=55.0,
        ),
        EventAlphaPolicyScenario(
            name="require_market_confirmation",
            opportunity_threshold=65.0,
            require_market_confirmation=True,
            require_impact_path_validated=False,
            allow_weak_macro_with_market=False,
            evidence_quality_minimum=60.0,
        ),
        EventAlphaPolicyScenario(
            name="require_impact_path_validated",
            opportunity_threshold=65.0,
            require_market_confirmation=False,
            require_impact_path_validated=True,
            allow_weak_macro_with_market=False,
            evidence_quality_minimum=60.0,
        ),
        EventAlphaPolicyScenario(
            name="high_quality_only",
            opportunity_threshold=75.0,
            require_market_confirmation=True,
            require_impact_path_validated=True,
            allow_weak_macro_with_market=False,
            evidence_quality_minimum=75.0,
        ),
        EventAlphaPolicyScenario(
            name="allow_weak_macro_with_market_confirmation",
            opportunity_threshold=65.0,
            require_market_confirmation=True,
            require_impact_path_validated=False,
            allow_weak_macro_with_market=True,
            evidence_quality_minimum=65.0,
        ),
    ]
)


def simulate_policy(
    rows: Iterable[Mapping[str, Any]],
    *,
    profile: str | None = None,
    scenarios: Iterable[EventAlphaPolicyScenario] = DEFAULT_SCENARIOS,
    include_legacy: bool = False,
    feedback_rows: Iterable[Mapping[str, Any]] = (),
    missed_rows: Iterable[Mapping[str, Any]] = (),
) -> EventAlphaPolicySimulationResult:
    raw_items = [_normalize(row) for row in rows if isinstance(row, Mapping)]
    feedback_by_key = _feedback_by_key(feedback_rows)
    raw_items = [_with_feedback(row, feedback_by_key) for row in raw_items]
    missed = [dict(row) for row in missed_rows if isinstance(row, Mapping)]
    legacy_conflicts = [
        row for row in raw_items
        if row.get("_snapshot_quality_classification") in _SIMULATOR_EXCLUDED_CLASSIFICATIONS
    ]
    items = [
        row for row in raw_items
        if include_legacy
        or row.get("_snapshot_quality_classification") not in _SIMULATOR_EXCLUDED_CLASSIFICATIONS
    ]
    baseline = tuple(_key(row) for row in items if _baseline_alertable(row))
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        selected = tuple(_key(row) for row in items if _passes(row, scenario))
        gained = tuple(sorted(set(selected) - set(baseline)))
        lost = tuple(sorted(set(baseline) - set(selected)))
        weak = tuple(
            _key(row)
            for row in items
            if _key(row) in selected and _is_weak_or_generic(row)
        )
        selected_items = [row for row in items if _key(row) in selected]
        useful = tuple(_key(row) for row in selected_items if row.get("feedback_label") == "useful")
        junk = tuple(_key(row) for row in selected_items if row.get("feedback_label") == "junk")
        results.append({
            "scenario": scenario.name,
            "opportunity_threshold": scenario.opportunity_threshold,
            "require_market_confirmation": scenario.require_market_confirmation,
            "require_impact_path_validated": scenario.require_impact_path_validated,
            "allow_weak_macro_with_market": scenario.allow_weak_macro_with_market,
            "evidence_quality_minimum": scenario.evidence_quality_minimum,
            "alertable_count": len(selected),
            "local_only_count": max(0, len(items) - len(selected)),
            "gained": gained,
            "lost": lost,
            "weak_or_generic_alertable": weak,
            "known_useful_selected": useful,
            "known_junk_selected": junk,
            "known_useful_count": len(useful),
            "known_junk_count": len(junk),
            "missed_recall_candidates": _missed_recall_candidates(missed, scenario),
            "quality_warnings": _quality_warnings(items, selected),
            "legacy_conflicts_excluded": 0 if include_legacy else len(legacy_conflicts),
        })
    return EventAlphaPolicySimulationResult(
        profile=profile,
        baseline_alertable=baseline,
        scenarios=tuple(results),
        legacy_conflicts_excluded=0 if include_legacy else len(legacy_conflicts),
    )


def format_policy_simulation(result: EventAlphaPolicySimulationResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA POLICY SIMULATION (artifact-only; no writes/sends)",
        "=" * 76,
        f"profile: {result.profile or 'default'}",
        f"baseline_alertable: {len(result.baseline_alertable)}",
        f"legacy_conflicts_excluded: {result.legacy_conflicts_excluded}",
        "",
    ]
    for row in result.scenarios:
        lines.append(
            f"{row['scenario']}: alertable={row['alertable_count']} "
            f"local_only={row['local_only_count']} gained={len(row['gained'])} lost={len(row['lost'])}"
        )
        if row["gained"]:
            lines.append("  gained: " + ", ".join(row["gained"][:6]))
        if row["lost"]:
            lines.append("  lost: " + ", ".join(row["lost"][:6]))
        if row["weak_or_generic_alertable"]:
            lines.append("  warning_weak_or_generic_alertable: " + ", ".join(row["weak_or_generic_alertable"][:6]))
        if row.get("known_junk_selected"):
            lines.append("  known_junk_selected: " + ", ".join(row["known_junk_selected"][:6]))
        if row.get("known_useful_selected"):
            lines.append("  known_useful_selected: " + ", ".join(row["known_useful_selected"][:6]))
        if row.get("missed_recall_candidates"):
            lines.append("  missed_recall_candidates: " + ", ".join(row["missed_recall_candidates"][:6]))
        if row.get("quality_warnings"):
            lines.append("  quality_warnings: " + "; ".join(row["quality_warnings"][:6]))
    lines.append("")
    lines.append("Simulation only; no alerts, notifications, trades, paper rows, live RSI rows, or watchlist state were written.")
    return "\n".join(lines).rstrip()


def _normalize(row: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    components = event_alpha_quality_fields.quality_components(data)
    data.update(event_alpha_quality_fields.ensure_quality_fields(data, components=components))
    if (
        data.get("row_type") == "event_alpha_alert_snapshot"
        or data.get("route")
        or data.get("final_route_after_quality_gate")
        or data.get("route_alertable") is not None
    ):
        data["_snapshot_quality_classification"] = event_alpha_alert_store.classify_alert_snapshot(data)
    else:
        data["_snapshot_quality_classification"] = event_alpha_alert_store.SNAPSHOT_CURRENT_CLEAN
    return data


def _feedback_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        label = str(row.get("label") or row.get("feedback_label") or "").strip()
        if not label:
            continue
        for key in _row_keys(row):
            out[key] = label
    return out


def _with_feedback(row: Mapping[str, Any], feedback_by_key: Mapping[str, str]) -> dict[str, Any]:
    out = dict(row)
    label = next((feedback_by_key[key] for key in _row_keys(out) if key in feedback_by_key), None)
    if label:
        out["feedback_label"] = label
    return out


def _row_keys(row: Mapping[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for field in (
        "key",
        "target",
        "feedback_target",
        "core_opportunity_id",
        "alert_key",
        "alert_id",
        "card_id",
        "hypothesis_id",
        "incident_id",
        "symbol",
        "coin_id",
        "asset_symbol",
        "asset_coin_id",
        "validated_symbol",
        "validated_coin_id",
    ):
        value = str(row.get(field) or "").strip()
        if not value:
            continue
        keys.append(value)
        if value.startswith("ea:"):
            keys.append(value[3:])
        else:
            keys.append(f"ea:{value}")
    return tuple(dict.fromkeys(keys))


def _missed_recall_candidates(rows: Iterable[Mapping[str, Any]], scenario: EventAlphaPolicyScenario) -> tuple[str, ...]:
    out: list[str] = []
    if scenario.name not in {"lower_opportunity_threshold", "allow_weak_macro_with_market_confirmation"}:
        return ()
    for row in rows:
        stage = str(row.get("failure_stage") or "")
        if stage in {"resolver_missed_asset", "candidate_not_resolved", "quality_gate_too_strict", "source_ingested_but_not_extracted"}:
            key = str(row.get("feedback_target") or row.get("symbol") or row.get("coin_id") or stage)
            out.append(key)
    return tuple(dict.fromkeys(out))


def _baseline_alertable(row: Mapping[str, Any]) -> bool:
    final_route = str(row.get("final_route_after_quality_gate") or "")
    if not final_route:
        components = row.get("score_components") if isinstance(row.get("score_components"), Mapping) else {}
        final_route, _ = event_alpha_router.quality_gate_route_for_row(
            row,
            components=components,
            require_quality=event_alpha_quality_fields.has_any_quality_field(row, components_key="score_components"),
        )
    explicit = row.get("alertable_after_quality_gate")
    if explicit is not None:
        return bool(explicit) and event_alpha_router.route_value_is_alertable(final_route)
    return event_alpha_router.route_value_is_alertable(final_route)


def _quality_warnings(rows: Iterable[Mapping[str, Any]], selected: Iterable[str]) -> tuple[str, ...]:
    selected_keys = set(selected)
    warnings: list[str] = []
    for row in rows:
        if _key(row) not in selected_keys:
            continue
        classification = str(row.get("_snapshot_quality_classification") or "")
        if classification in {
            event_alpha_alert_store.SNAPSHOT_LEGACY_CONFLICT,
            event_alpha_alert_store.SNAPSHOT_MISSING_FINAL_ROUTE,
            event_alpha_alert_store.SNAPSHOT_STALE_PRE_QUALITY_GATE,
        }:
            warnings.append(f"{_key(row)}:{classification}")
    return tuple(dict.fromkeys(warnings))


def _passes(row: Mapping[str, Any], scenario: EventAlphaPolicyScenario) -> bool:
    generic = str(row.get("impact_path_type") or "") == "generic_cooccurrence_only"
    weak = _is_weak_or_generic(row)
    if generic:
        return False
    if weak and not scenario.allow_weak_macro_with_market:
        return False
    if float(row.get("opportunity_score_final") or row.get("opportunity_score_v2") or row.get("latest_score") or 0) < scenario.opportunity_threshold:
        return False
    if float(row.get("evidence_quality_score") or 0) < scenario.evidence_quality_minimum:
        return False
    market_level = str(row.get("market_confirmation_level") or "")
    if scenario.require_market_confirmation and market_level not in {"moderate", "strong"}:
        return False
    if weak and scenario.allow_weak_macro_with_market and market_level not in {"strong"}:
        return False
    if scenario.require_impact_path_validated:
        if str(row.get("validation_stage") or "") not in {"impact_path_validated", "market_confirmed", "promoted_to_radar"}:
            return False
        if str(row.get("impact_path_strength") or "") not in {"medium", "strong"}:
            return False
    return True


def _is_weak_or_generic(row: Mapping[str, Any]) -> bool:
    return (
        str(row.get("impact_path_type") or "") == "generic_cooccurrence_only"
        or str(row.get("impact_path_strength") or "") in {"weak", "none"}
        or "generic_cooccurrence" in str(row.get("why_local_only") or "")
    )


def _key(row: Mapping[str, Any]) -> str:
    return str(
        row.get("alert_id")
        or row.get("alert_key")
        or row.get("key")
        or row.get("hypothesis_id")
        or row.get("symbol")
        or row.get("coin_id")
        or "candidate"
    )
