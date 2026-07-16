"""Outcome-blind operator-notification burden simulation for replay research.

The simulator consumes episode representative rows only.  It never reads an
outcome, ranks by realized performance, mutates notification policy, or emits a
notification.  Scenario choices are the closed budgets in the frozen
empirical-validation protocol; callers cannot supply alternative limits.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from . import empirical_validation_protocol


SCHEMA_ID = "decision_radar.empirical_operator_notification_burden"
SCHEMA_VERSION = 1
METHOD = "frozen_episode_representative_outcome_blind_burden_simulation"

_ZERO_SAFETY = {
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "notifications": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
}
_OPTIONAL_OPERATOR_FIELDS = {
    "digest": ("digest_eligible",),
    "review": ("review_required",),
    "system_warning": ("system_warning",),
    "calendar_reminder": ("calendar_reminder",),
}
_MATERIAL_CHANGE_BOOL_FIELDS = (
    "operator_material_change",
    "material_change",
)


def build_operator_notification_burden(
    representatives: Iterable[Mapping[str, Any]],
    *,
    partition: str,
    evidence_mode: str,
) -> dict[str, Any]:
    """Describe current burden and simulate the frozen notification budgets."""

    protocol = _frozen_protocol()
    if not isinstance(partition, str) or not partition.strip():
        raise ValueError("partition_required")
    if not isinstance(evidence_mode, str) or not evidence_mode.strip():
        raise ValueError("evidence_mode_required")

    raw_rows = list(representatives)
    rows = [
        _normalize_row(row, position=position)
        for position, row in enumerate(raw_rows)
        if isinstance(row, Mapping)
    ]
    rows.sort(key=_row_order)
    visible = [row for row in rows if row["_visible"] is True]
    budgets = protocol["operator_burden"]["budgets"]
    descriptive_minimum = int(protocol["minimum_samples"]["descriptive"])

    days = _group(rows, lambda row: row["_day"])
    families = _group(rows, lambda row: row["_family"])
    daily = [
        _burden_row(
            "day",
            name,
            grouped,
            partition=partition,
            evidence_mode=evidence_mode,
        )
        for name, grouped in sorted(days.items())
    ]
    family_rows = [
        _burden_row(
            "family",
            name,
            grouped,
            partition=partition,
            evidence_mode=evidence_mode,
        )
        for name, grouped in sorted(families.items())
    ]
    optional = {
        name: _optional_field_summary(visible, fields)
        for name, fields in _OPTIONAL_OPERATOR_FIELDS.items()
    }
    lifetime = _lifetime_summary(visible)
    material_intervals = _material_change_interval_summary(visible)
    urgent = [row for row in visible if row["_urgent"] is True]
    sample_status = _sample_status(len(visible), descriptive_minimum)
    invalid_input_count = len(raw_rows) - len(rows)

    result: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": empirical_validation_protocol.protocol_sha256(protocol),
        "partition": partition.strip(),
        "evidence_mode": evidence_mode.strip(),
        "input_basis": "episode_representatives_only",
        "selection_basis": "point_in_time_operator_fields_only",
        "input_row_count": len(raw_rows),
        "episode_count": len(rows),
        "invalid_non_mapping_input_count": invalid_input_count,
        "visible_episode_count": len(visible),
        "hidden_episode_count": sum(row["_visible"] is False for row in rows),
        "visibility_missing_count": sum(row["_visible"] is None for row in rows),
        "urgent_visible_episode_count": len(urgent),
        "urgent_status_missing_count": sum(
            row["_urgent"] is None for row in visible
        ),
        "observed_day_count": len(daily),
        "family_count": len(family_rows),
        "mean_ideas_per_observed_day": len(rows) / len(daily) if daily else None,
        "mean_visible_ideas_per_observed_day": (
            len(visible) / len(daily) if daily else None
        ),
        "dependent_repeat_item_count": sum(row["_dependent_repeats"] for row in rows),
        "visible_dependent_repeat_item_count": sum(
            row["_dependent_repeats"] for row in visible
        ),
        "daily": daily,
        "families": family_rows,
        "optional_operator_state": optional,
        "idea_lifetime_and_expiry": lifetime,
        "material_change_intervals": material_intervals,
        "sample_status": sample_status,
        "input_status": _input_status(
            rows,
            invalid_input_count=invalid_input_count,
            visible_count=len(visible),
        ),
        "frozen_budgets": {
            "urgent_per_cycle": list(budgets["urgent_per_cycle"]),
            "urgent_per_day": list(budgets["urgent_per_day"]),
            "one_item_per_visible_family": bool(
                budgets["one_item_per_visible_family"]
            ),
            "material_change_only": bool(budgets["material_change_only"]),
            "cooldown_hours": list(budgets["cooldown_hours"]),
        },
        "simulations": {
            "urgent_per_cycle": [
                _cap_simulation(
                    urgent,
                    limit=int(limit),
                    scope="observation_cycle",
                    key=lambda row: row["_cycle"],
                )
                for limit in budgets["urgent_per_cycle"]
            ],
            "urgent_per_day": [
                _cap_simulation(
                    urgent,
                    limit=int(limit),
                    scope="calendar_day_utc",
                    key=lambda row: row["_day"],
                )
                for limit in budgets["urgent_per_day"]
            ],
            "one_item_per_visible_family": _one_family_per_cycle(visible),
            "family_cooldown": [
                _cooldown_simulation(visible, hours=int(hours))
                for hours in budgets["cooldown_hours"]
            ],
            "material_change_only": _material_change_simulation(visible),
        },
        "simulation_scenario_count": (
            len(budgets["urgent_per_cycle"])
            + len(budgets["urgent_per_day"])
            + len(budgets["cooldown_hours"])
            + 2
        ),
        "outcomes_used_for_selection": 0,
        "outcome_fields_read": [],
        "notification_state_inferred": False,
        "causal_claim": False,
        "production_policy_claim": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
        "safety": dict(_ZERO_SAFETY),
    }
    return result


def _frozen_protocol() -> dict[str, Any]:
    protocol = empirical_validation_protocol.protocol_values()
    errors = empirical_validation_protocol.validate_protocol(protocol)
    if errors:
        raise ValueError("frozen_protocol_invalid:" + ";".join(errors))
    return protocol


def _normalize_row(row: Mapping[str, Any], *, position: int) -> dict[str, Any]:
    value = dict(row)
    projection = row.get("decision_projection")
    if isinstance(projection, Mapping):
        for key, item in projection.items():
            value.setdefault(str(key), item)
    aliases = {
        "operator_visible_idea": "operator_visible",
        "anomaly_family": "candidate_family_id",
    }
    for target, source in aliases.items():
        if target not in value and source in value:
            value[target] = value[source]

    observed = _aware_datetime(value.get("observed_at"))
    visible = _optional_bool(value, ("operator_visible_idea", "operator_visible"))
    urgent, urgent_basis = _urgent_state(value)
    family = _family(value)
    episode_id = _text(value.get("episode_id")) or f"missing_episode_id:{position}"
    value.update(
        {
            "_episode_id": episode_id,
            "_observed": observed,
            "_day": observed.date().isoformat() if observed else "unknown_date",
            "_cycle": observed.isoformat() if observed else f"unknown_cycle:{episode_id}",
            "_family": family,
            "_visible": visible,
            "_urgent": urgent,
            "_urgent_basis": urgent_basis,
            "_dependent_repeats": _repeat_count(value),
        }
    )
    return value


def _burden_row(
    dimension: str,
    name: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    partition: str,
    evidence_mode: str,
) -> dict[str, Any]:
    visible = [row for row in rows if row["_visible"] is True]
    family_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        family_counts[str(row["_family"])] += 1
    dependent = sum(int(row["_dependent_repeats"]) for row in rows)
    independent_repeats = sum(max(0, count - 1) for count in family_counts.values())
    observation_intervals = _observation_intervals(rows)
    material_intervals = _material_change_interval_summary(visible)
    lifetime = _lifetime_summary(visible)
    optional = {
        field: _optional_field_summary(visible, aliases)
        for field, aliases in _OPTIONAL_OPERATOR_FIELDS.items()
    }
    return {
        "dimension": dimension,
        "name": name,
        "partition": partition,
        "evidence_mode": evidence_mode,
        "idea_count": len(rows),
        "visible_idea_count": len(visible),
        "visibility_missing_count": sum(row["_visible"] is None for row in rows),
        "urgent_item_count": sum(row["_urgent"] is True for row in visible),
        "urgent_status_missing_count": sum(row["_urgent"] is None for row in visible),
        "digest_item_count": optional["digest"]["true_count"],
        "digest_status_missing_count": optional["digest"]["missing_count"],
        "dependent_repeat_item_count": dependent,
        "repeated_family_item_count": dependent + independent_repeats,
        "observation_interval_sample_size": len(observation_intervals),
        "median_observation_interval_hours": (
            statistics.median(observation_intervals)
            if observation_intervals
            else None
        ),
        "material_change_interval_status": material_intervals["status"],
        "material_change_interval_sample_size": material_intervals["available_count"],
        "median_material_change_interval_hours": material_intervals["median_hours"],
        "idea_lifetime_sample_size": lifetime["available_count"],
        "median_idea_lifetime_hours": lifetime["median_hours"],
        "expiry_status_missing_count": lifetime["missing_count"],
        "expiry_status_invalid_count": lifetime["invalid_count"],
        "review_required_count": optional["review"]["true_count"],
        "review_status_missing_count": optional["review"]["missing_count"],
        "system_warning_count": optional["system_warning"]["true_count"],
        "system_warning_status_missing_count": optional["system_warning"]["missing_count"],
        "calendar_reminder_count": optional["calendar_reminder"]["true_count"],
        "calendar_reminder_status_missing_count": optional["calendar_reminder"]["missing_count"],
        "optional_operator_state": optional,
        "notification_state_inferred": False,
        "policy_eligible": False,
        "research_only": True,
        "auto_apply": False,
    }


def _cap_simulation(
    rows: Sequence[Mapping[str, Any]],
    *,
    limit: int,
    scope: str,
    key: Any,
) -> dict[str, Any]:
    grouped = _group(rows, key)
    retained = sum(min(limit, len(group)) for group in grouped.values())
    return _scenario_counts(
        eligible=len(rows),
        retained=retained,
        scenario="urgent_cap",
        parameters={"limit": limit, "scope": scope},
        group_count=len(grouped),
        selection_rule="stable_point_in_time_order_no_outcome_ranking",
    )


def _one_family_per_cycle(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    missing_family = 0
    for row in rows:
        family = str(row["_family"])
        if family == "unknown":
            family = f"unknown:{row['_episode_id']}"
            missing_family += 1
        groups[(str(row["_cycle"]), family)].append(row)
    retained = len(groups)
    return _scenario_counts(
        eligible=len(rows),
        retained=retained,
        scenario="one_item_per_visible_family",
        parameters={"scope": "observation_cycle", "limit_per_family": 1},
        group_count=len(groups),
        selection_rule="first_stable_point_in_time_family_item_no_outcome_ranking",
        extra={"family_missing_count_retained_unsuppressed": missing_family},
    )


def _cooldown_simulation(
    rows: Sequence[Mapping[str, Any]],
    *,
    hours: int,
) -> dict[str, Any]:
    last_retained: dict[str, datetime] = {}
    retained = 0
    missing_context = 0
    for row in rows:
        family = str(row["_family"])
        observed = row["_observed"]
        if family == "unknown" or not isinstance(observed, datetime):
            retained += 1
            missing_context += 1
            continue
        prior = last_retained.get(family)
        if prior is None or (observed - prior).total_seconds() >= hours * 3600:
            retained += 1
            last_retained[family] = observed
    return _scenario_counts(
        eligible=len(rows),
        retained=retained,
        scenario="family_cooldown",
        parameters={"cooldown_hours": hours, "scope": "across_observation_cycles"},
        group_count=len({str(row["_family"]) for row in rows}),
        selection_rule="first_then_elapsed_cooldown_no_outcome_ranking",
        extra={"missing_family_or_time_count_retained_unsuppressed": missing_context},
    )


def _material_change_simulation(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    dependent_total = sum(int(row["_dependent_repeats"]) for row in rows)
    baseline = len(rows) + dependent_total
    if dependent_total == 0:
        return {
            "scenario": "material_change_only",
            "status": "unavailable_no_dependent_progression_evidence",
            "available": False,
            "eligible_count": baseline,
            "retained_count": None,
            "suppressed_count": None,
            "burden_reduction_count": None,
            "burden_reduction_fraction": None,
            "dependent_repeat_count": 0,
            "progression_missing_count": 0,
            "material_change_state_missing_count": 0,
            "selection_rule": "explicit_material_change_state_only_never_infer",
            "outcomes_used_for_selection": 0,
        }

    retained = len(rows)
    progression_missing = 0
    state_missing = 0
    for row in rows:
        repeat_count = int(row["_dependent_repeats"])
        if repeat_count == 0:
            continue
        progression = _progression(row)
        if progression is None or len(progression) < repeat_count + 1:
            progression_missing += repeat_count
            continue
        dependent = progression[1 : repeat_count + 1]
        for item in dependent:
            state = _explicit_material_change(item)
            if state is None:
                state_missing += 1
            elif state:
                retained += 1
    if progression_missing or state_missing:
        return {
            "scenario": "material_change_only",
            "status": "unavailable_progression_or_material_change_state_missing",
            "available": False,
            "eligible_count": baseline,
            "retained_count": None,
            "suppressed_count": None,
            "burden_reduction_count": None,
            "burden_reduction_fraction": None,
            "dependent_repeat_count": dependent_total,
            "progression_missing_count": progression_missing,
            "material_change_state_missing_count": state_missing,
            "selection_rule": "explicit_material_change_state_only_never_infer",
            "outcomes_used_for_selection": 0,
        }
    result = _scenario_counts(
        eligible=baseline,
        retained=retained,
        scenario="material_change_only",
        parameters={"dependent_repeat_count": dependent_total},
        group_count=len(rows),
        selection_rule="initial_representative_plus_explicit_material_changes_only",
    )
    result["available"] = True
    result["progression_missing_count"] = 0
    result["material_change_state_missing_count"] = 0
    return result


def _scenario_counts(
    *,
    eligible: int,
    retained: int,
    scenario: str,
    parameters: Mapping[str, Any],
    group_count: int,
    selection_rule: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    suppressed = eligible - retained
    result = {
        "scenario": scenario,
        "status": "ready" if eligible else "no_sample",
        "available": True,
        "parameters": dict(parameters),
        "group_count": group_count,
        "eligible_count": eligible,
        "retained_count": retained,
        "suppressed_count": suppressed,
        "burden_reduction_count": suppressed,
        "burden_reduction_fraction": suppressed / eligible if eligible else None,
        "selection_rule": selection_rule,
        "outcomes_used_for_selection": 0,
    }
    if extra:
        result.update(extra)
    return result


def _optional_field_summary(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> dict[str, Any]:
    states = [_optional_bool(row, fields) for row in rows]
    true_count = sum(value is True for value in states)
    false_count = sum(value is False for value in states)
    missing_count = sum(value is None for value in states)
    return {
        "status": (
            "no_sample"
            if not rows
            else "unavailable"
            if missing_count == len(rows)
            else "partial"
            if missing_count
            else "available"
        ),
        "sample_count": len(rows),
        "true_count": true_count,
        "false_count": false_count,
        "missing_count": missing_count,
        "inferred_count": 0,
    }


def _lifetime_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    lifetimes: list[float] = []
    missing = 0
    invalid = 0
    for row in rows:
        observed = row["_observed"]
        expires = _aware_datetime(row.get("expires_at"))
        if not isinstance(observed, datetime) or expires is None:
            missing += 1
            continue
        if expires < observed:
            invalid += 1
            continue
        lifetimes.append((expires - observed).total_seconds() / 3600.0)
    return {
        "status": (
            "no_sample"
            if not rows
            else "unavailable"
            if not lifetimes and missing == len(rows)
            else "partial"
            if missing or invalid
            else "available"
        ),
        "sample_count": len(rows),
        "available_count": len(lifetimes),
        "missing_count": missing,
        "invalid_count": invalid,
        "minimum_hours": min(lifetimes) if lifetimes else None,
        "median_hours": statistics.median(lifetimes) if lifetimes else None,
        "maximum_hours": max(lifetimes) if lifetimes else None,
    }


def _material_change_interval_summary(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    dependent_total = sum(int(row["_dependent_repeats"]) for row in rows)
    if not rows:
        return _material_interval_result("no_sample")
    if dependent_total == 0:
        return _material_interval_result(
            "unavailable_no_dependent_progression_evidence",
            dependent_repeat_count=0,
        )

    intervals: list[float] = []
    progression_missing = 0
    state_missing = 0
    timestamp_missing = 0
    for row in rows:
        repeats = int(row["_dependent_repeats"])
        if repeats == 0:
            continue
        progression = _progression(row)
        if progression is None or len(progression) < repeats + 1:
            progression_missing += repeats
            continue
        selected_times: list[datetime] = []
        for index, member in enumerate(progression[: repeats + 1]):
            changed = True if index == 0 else _explicit_material_change(member)
            if changed is None:
                state_missing += 1
                continue
            if not changed:
                continue
            observed = _aware_datetime(member.get("observed_at"))
            if observed is None:
                timestamp_missing += 1
                continue
            selected_times.append(observed)
        selected_times.sort()
        intervals.extend(
            (current - prior).total_seconds() / 3600.0
            for prior, current in zip(selected_times, selected_times[1:])
        )
    if progression_missing or state_missing or timestamp_missing:
        return _material_interval_result(
            "unavailable_incomplete_progression_evidence",
            dependent_repeat_count=dependent_total,
            progression_missing_count=progression_missing,
            material_change_state_missing_count=state_missing,
            timestamp_missing_count=timestamp_missing,
        )
    return _material_interval_result(
        "available" if intervals else "available_no_interval",
        intervals=intervals,
        dependent_repeat_count=dependent_total,
    )


def _material_interval_result(
    status: str,
    *,
    intervals: Sequence[float] = (),
    dependent_repeat_count: int = 0,
    progression_missing_count: int = 0,
    material_change_state_missing_count: int = 0,
    timestamp_missing_count: int = 0,
) -> dict[str, Any]:
    return {
        "status": status,
        "dependent_repeat_count": dependent_repeat_count,
        "available_count": len(intervals),
        "progression_missing_count": progression_missing_count,
        "material_change_state_missing_count": material_change_state_missing_count,
        "timestamp_missing_count": timestamp_missing_count,
        "minimum_hours": min(intervals) if intervals else None,
        "median_hours": statistics.median(intervals) if intervals else None,
        "maximum_hours": max(intervals) if intervals else None,
        "inferred_count": 0,
    }


def _progression(row: Mapping[str, Any]) -> list[Mapping[str, Any]] | None:
    for field in ("episode_member_progression", "member_progression"):
        value = row.get(field)
        if isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
            return value
    return None


def _explicit_material_change(row: Mapping[str, Any]) -> bool | None:
    state = _optional_bool(row, _MATERIAL_CHANGE_BOOL_FIELDS)
    if state is not None:
        return state
    if "material_change_reasons" not in row:
        return None
    reasons = row.get("material_change_reasons")
    if isinstance(reasons, (list, tuple)):
        return bool(reasons)
    return None


def _urgent_state(row: Mapping[str, Any]) -> tuple[bool | None, str]:
    explicit = _optional_bool(row, ("operator_urgent", "urgent"))
    if explicit is not None:
        return explicit, "explicit_operator_urgent_state"
    route = _text(row.get("radar_route"))
    if route:
        return route == "rapid_market_anomaly", "frozen_route_semantics"
    return None, "unavailable"


def _optional_bool(row: Mapping[str, Any], fields: Sequence[str]) -> bool | None:
    for field in fields:
        value = row.get(field)
        if isinstance(value, bool):
            return value
    return None


def _repeat_count(row: Mapping[str, Any]) -> int:
    explicit = row.get("dependent_repeat_count")
    if type(explicit) is int and explicit >= 0:
        return explicit
    members = row.get("episode_member_count")
    return max(0, members - 1) if type(members) is int and members >= 1 else 0


def _family(row: Mapping[str, Any]) -> str:
    for field in (
        "anomaly_family",
        "family_id",
        "episode_family",
        "candidate_family_id",
        "anomaly_type",
    ):
        value = _text(row.get(field))
        if value:
            return value
    return "unknown"


def _observation_intervals(rows: Sequence[Mapping[str, Any]]) -> list[float]:
    times = sorted(
        row["_observed"]
        for row in rows
        if isinstance(row["_observed"], datetime)
    )
    return [
        (current - prior).total_seconds() / 3600.0
        for prior, current in zip(times, times[1:])
    ]


def _group(rows: Sequence[Mapping[str, Any]], key: Any) -> dict[str, list[Mapping[str, Any]]]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(key(row))].append(row)
    return groups


def _row_order(row: Mapping[str, Any]) -> tuple[datetime, str, str]:
    observed = row["_observed"]
    if not isinstance(observed, datetime):
        observed = datetime.max.replace(tzinfo=timezone.utc)
    return observed, str(row["_family"]), str(row["_episode_id"])


def _aware_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _sample_status(count: int, descriptive_minimum: int) -> dict[str, Any]:
    if count == 0:
        return {
            "status": "no_sample",
            "evidence_strength": "no_evidence",
            "sample_size": 0,
            "descriptive_minimum": descriptive_minimum,
        }
    if count < descriptive_minimum:
        return {
            "status": "insufficient_sample",
            "evidence_strength": "insufficient",
            "sample_size": count,
            "descriptive_minimum": descriptive_minimum,
        }
    return {
        "status": "descriptive_sample",
        "evidence_strength": "descriptive_only",
        "sample_size": count,
        "descriptive_minimum": descriptive_minimum,
    }


def _input_status(
    rows: Sequence[Mapping[str, Any]],
    *,
    invalid_input_count: int,
    visible_count: int,
) -> str:
    if not rows and not invalid_input_count:
        return "no_input"
    if not rows:
        return "invalid_input_only"
    if invalid_input_count:
        return "partial_invalid_input"
    if not visible_count:
        return "no_visible_sample"
    return "ready"


def _text(value: Any) -> str:
    return str(value).strip().casefold() if value not in (None, "") else ""


__all__ = [
    "METHOD",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "build_operator_notification_burden",
]
