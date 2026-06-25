"""Offline policy-threshold simulation for Event Alpha quality artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from . import event_alpha_quality_fields


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
) -> EventAlphaPolicySimulationResult:
    items = [_normalize(row) for row in rows if isinstance(row, Mapping)]
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
        })
    return EventAlphaPolicySimulationResult(profile=profile, baseline_alertable=baseline, scenarios=tuple(results))


def format_policy_simulation(result: EventAlphaPolicySimulationResult) -> str:
    lines = [
        "=" * 76,
        "EVENT ALPHA POLICY SIMULATION (artifact-only; no writes/sends)",
        "=" * 76,
        f"profile: {result.profile or 'default'}",
        f"baseline_alertable: {len(result.baseline_alertable)}",
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
    lines.append("")
    lines.append("Simulation only; no alerts, notifications, trades, paper rows, live RSI rows, or watchlist state were written.")
    return "\n".join(lines).rstrip()


def _normalize(row: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    components = event_alpha_quality_fields.quality_components(data)
    data.update(event_alpha_quality_fields.ensure_quality_fields(data, components=components))
    return data


def _baseline_alertable(row: Mapping[str, Any]) -> bool:
    route = str(row.get("route") or "")
    tier = str(row.get("tier") or row.get("latest_tier") or "")
    level = str(row.get("opportunity_level") or "")
    return (
        route in {"RESEARCH_DIGEST", "HIGH_PRIORITY_RESEARCH", "TRIGGERED_FADE_RESEARCH"}
        or tier in {"RADAR_DIGEST", "WATCHLIST", "HIGH_PRIORITY_WATCH", "TRIGGERED_FADE"}
        or level in {"validated_digest", "watchlist", "high_priority"}
    )


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
