"""Closed validation for immutable Empirical Lab diagnostic artifacts."""

from __future__ import annotations

import hashlib
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from . import empirical_replay_analysis
from . import empirical_replay_store
from . import empirical_validation_protocol


ROUTE_CALIBRATION_SCHEMA_ID = "decision_radar.empirical_route_conditioned_calibration"
MARKET_RISK_SCHEMA_ID = "decision_radar.empirical_market_wide_risk_diagnostics"
SCHEMA_VERSION = 1
ROUTES = empirical_replay_analysis.ROUTES
SCORE_FIELDS = empirical_replay_analysis.SCORE_FIELDS
SCORE_BUCKETS = empirical_replay_analysis.SCORE_BUCKETS
SCORE_EXPECTATIONS = empirical_replay_analysis.SCORE_EXPECTATIONS
CONDITIONING_DIMENSIONS = (
    "directional_bias",
    "market_regime",
    "liquidity_tier",
    "data_quality_mode",
)
SELECTION_PARTITIONS = ("development", "validation")
AFFECTED_ASSET_LIMITS = (3, 5, 10)
CORRELATED_FAMILY_STATUS = "not_evaluable_missing_correlation_and_family_lineage"

_HEX = frozenset("0123456789abcdef")
_ZERO_SAFETY = {
    "provider_calls": 0,
    "authorization_mutations": 0,
    "telegram_sends": 0,
    "trades": 0,
    "orders": 0,
    "event_alpha_paper_trades": 0,
    "normal_rsi_writes": 0,
    "event_alpha_triggered_fade": 0,
    "dashboard_authority_mutations": 0,
    "production_policy_mutations": 0,
}


def validate_route_conditioned_calibration(
    value: Mapping[str, Any], *, source_run_fingerprint: str | None = None
) -> dict[str, Any]:
    """Validate every closed field and reconciliation in calibration output."""

    fields = "schema_id schema_version method source_run_fingerprint partitions partition_policy input_basis archive_record_digests_preverified representative_join episode_count idea_record_count episode_record_count score_fields score_buckets minimum_samples route_score_diagnostics partition_route_score_diagnostics partition_route_score_diagnostic_count partition_route_score_diagnostics_closed route_conditioned_dimension_cohorts between_route_bucket_composition composition_reconciliation multiple_comparison_warning outcome_unit probabilistic_calibration_claim causal_claim model_changed production_policy_claim policy_eligible research_only auto_apply safety diagnostic_digest".split()
    row = _validated_diagnostic(
        value, fields, ROUTE_CALIBRATION_SCHEMA_ID, source_run_fingerprint
    )
    protocol = _protocol()
    _false_fields(row, "probabilistic_calibration_claim")
    if (
        row["method"] != "route_conditioned_fixed_bucket_descriptive_diagnostics"
        or row["score_fields"] != list(SCORE_FIELDS)
        or row["outcome_unit"] != "direction_adjusted_return_fraction"
        or _nat(row["episode_record_count"]) != row["episode_count"]
        or _nat(row["idea_record_count"]) < row["episode_count"]
    ):
        raise ValueError("route_calibration_contract_invalid")
    _validate_bucket_definitions(row["score_buckets"])
    minimums = _closed(
        row["minimum_samples"],
        "adjacent_bucket_comparison_each_bucket cohort_directional below_cohort_directional_status".split(),
        "minimum_samples",
    )
    if (
        _nat(minimums["adjacent_bucket_comparison_each_bucket"])
        != protocol["minimum_samples"]["descriptive"]
        or _nat(minimums["cohort_directional"])
        != protocol["minimum_samples"]["cohort_directional"]
        or minimums["below_cohort_directional_status"]
        != "insufficient_exploratory"
        or row["multiple_comparison_warning"]
        != protocol["statistics"]["multiple_comparison_policy"]
    ):
        raise ValueError("route_calibration_fixed_values_invalid")
    routes = _score_groups(
        row["route_score_diagnostics"],
        [(route, "route", route) for route in ROUTES],
    )
    partition_keys = [
        (partition, route, "route", route)
        for partition in SELECTION_PARTITIONS
        for route in ROUTES
    ]
    partition_rows = _score_groups(
        row["partition_route_score_diagnostics"],
        partition_keys,
        partitioned=True,
    )
    if (
        _nat(row["partition_route_score_diagnostic_count"]) != len(partition_keys)
        or row["partition_route_score_diagnostics_closed"] is not True
    ):
        raise ValueError("partition_route_diagnostics_not_closed")
    for route in ROUTES:
        if routes[route] != sum(
            partition_rows[(partition, route)] for partition in SELECTION_PARTITIONS
        ):
            raise ValueError("partition_route_episode_count_mismatch")
    conditioned = _closed_list(
        row["route_conditioned_dimension_cohorts"], 4096, "conditioned_cohorts"
    )
    observed: dict[tuple[str, str], set[str]] = defaultdict(set)
    counts: Counter[tuple[str, str]] = Counter()
    seen: set[tuple[str, str, str]] = set()
    for group in conditioned:
        _validate_score_group(group)
        key = (
            str(group["route"]),
            str(group["conditioning_dimension"]),
            str(group["conditioning_value"]),
        )
        if (
            key in seen
            or key[0] not in ROUTES
            or key[1] not in CONDITIONING_DIMENSIONS
            or not key[2]
        ):
            raise ValueError("conditioned_cohort_identity_invalid")
        seen.add(key)
        observed[(key[0], key[1])].add(key[2])
        counts[(key[0], key[1])] += group["episode_count"]
    for dimension in CONDITIONING_DIMENSIONS:
        inventory = observed[(ROUTES[0], dimension)]
        if "unknown" not in inventory or any(
            observed[(route, dimension)] != inventory
            or counts[(route, dimension)] != routes[route]
            for route in ROUTES
        ):
            raise ValueError("conditioned_cohort_closure_invalid")
    _validate_composition(row, routes)
    return dict(row)


def validate_market_wide_risk_diagnostics(
    value: Mapping[str, Any], *, source_run_fingerprint: str | None = None
) -> dict[str, Any]:
    """Validate every closed field and reconciliation in market-risk output."""

    fields = "schema_id schema_version method source_run_fingerprint partitions partition_policy input_basis archive_record_digests_preverified representative_join risk_item_rule episode_count risk_item_count risk_observed_day_count market_wide_group_count minimum_distinct_assets_for_market_wide_group affected_asset_limits affected_asset_ranking daily_risk_groups regime_conditioned_visibility correlated_family_suppression_status correlated_family_suppression_applied outcomes_used_for_group_formation outcome_fields_read_for_group_formation causal_claim model_changed production_policy_claim policy_eligible research_only auto_apply safety diagnostic_digest".split()
    row = _validated_diagnostic(
        value, fields, MARKET_RISK_SCHEMA_ID, source_run_fingerprint
    )
    ranking = [
        "return_24h_most_negative_missing_last",
        "volume_zscore_24h_highest_missing_last",
        "liquidity_usd_highest_missing_last",
        "canonical_asset_id_ascending",
    ]
    limits = row["affected_asset_limits"]
    if not isinstance(limits, list) or [
        _nat(limit) for limit in limits
    ] != list(AFFECTED_ASSET_LIMITS):
        raise ValueError("market_risk_affected_asset_limits_invalid")
    fixed = (
        row["method"] == "outcome_blind_exact_utc_day_cross_asset_risk_grouping"
        and row["risk_item_rule"] == "representative_radar_route_equals_risk_watch"
        and row["affected_asset_ranking"] == ranking
        and _nat(row["minimum_distinct_assets_for_market_wide_group"])
        == AFFECTED_ASSET_LIMITS[0]
        and row["correlated_family_suppression_status"]
        == CORRELATED_FAMILY_STATUS
    )
    if not fixed or _nat(row["risk_item_count"]) > row["episode_count"]:
        raise ValueError("market_risk_contract_invalid")
    _false_fields(
        row,
        "correlated_family_suppression_applied outcomes_used_for_group_formation outcome_fields_read_for_group_formation causal_claim model_changed production_policy_claim policy_eligible auto_apply",
    )
    _nat(row["risk_observed_day_count"])
    _nat(row["market_wide_group_count"])
    days = _closed_list(
        row["daily_risk_groups"], row["risk_item_count"], "daily_risk_groups"
    )
    identities: list[tuple[str, str]] = []
    total_items = 0
    formed = 0
    for day in days:
        _closed(
            day,
            "partition utc_day day_basis risk_item_count distinct_asset_count dependent_same_asset_item_count market_wide_episode_status affected_asset_lists ranked_asset_evidence market_regime_counts market_regime_status correlated_family_suppression_status correlated_family_suppression_applied outcomes_used_for_group_formation policy_eligible auto_apply".split(),
            "daily_risk_group",
        )
        partition, utc_day = day["partition"], day["utc_day"]
        if (
            partition not in SELECTION_PARTITIONS
            or not isinstance(utc_day, str)
            or _utc_day(utc_day + "T00:00:00Z") != utc_day
        ):
            raise ValueError("daily_risk_group_identity_invalid")
        identities.append((partition, utc_day))
        items = _nat(day["risk_item_count"])
        distinct = _nat(day["distinct_asset_count"])
        if (
            day["day_basis"]
            != "representative_observed_at_normalized_to_utc_date"
            or not 0 < distinct <= items
            or _nat(day["dependent_same_asset_item_count"]) != items - distinct
        ):
            raise ValueError("daily_risk_group_counts_invalid")
        formed_now = distinct >= AFFECTED_ASSET_LIMITS[0]
        if day["market_wide_episode_status"] != (
            "formed" if formed_now else "insufficient_distinct_assets"
        ):
            raise ValueError("daily_risk_group_status_invalid")
        assets = _validate_risk_assets(
            day["ranked_asset_evidence"], partition, distinct
        )
        _validate_affected_asset_lists(day["affected_asset_lists"], assets, distinct)
        regimes = day["market_regime_counts"]
        if (
            not isinstance(regimes, Mapping)
            or not regimes
            or any(
                not isinstance(key, str) or not key or key != _token(key)
                for key in regimes
            )
            or sum(_nat(count) for count in regimes.values()) != items
        ):
            raise ValueError("daily_risk_regime_counts_invalid")
        if (
            day["market_regime_status"]
            != ("consistent" if len(regimes) == 1 else "mixed")
            or day["correlated_family_suppression_status"]
            != CORRELATED_FAMILY_STATUS
        ):
            raise ValueError("daily_risk_fixed_status_invalid")
        _false_fields(
            day,
            "correlated_family_suppression_applied outcomes_used_for_group_formation policy_eligible auto_apply",
        )
        total_items += items
        formed += formed_now
    if (
        identities != sorted(set(identities))
        or row["risk_observed_day_count"] != len(days)
        or row["market_wide_group_count"] != formed
        or row["risk_item_count"] != total_items
    ):
        raise ValueError("daily_risk_group_reconciliation_invalid")
    _validate_regime_visibility(row, days)
    return dict(row)


def _validated_diagnostic(
    value: Mapping[str, Any],
    fields: Sequence[str],
    schema_id: str,
    source_run_fingerprint: str | None,
) -> dict[str, Any]:
    row = dict(_closed(value, fields, "diagnostic"))
    digest = _fingerprint(row["diagnostic_digest"])
    payload = {key: item for key, item in row.items() if key != "diagnostic_digest"}
    if digest != _digest(payload):
        raise ValueError("diagnostic_digest_mismatch")
    fingerprint = _fingerprint(row["source_run_fingerprint"])
    if source_run_fingerprint is not None and fingerprint != _fingerprint(
        source_run_fingerprint
    ):
        raise ValueError("diagnostic_source_run_fingerprint_mismatch")
    if (
        row["schema_id"] != schema_id
        or _nat(row["schema_version"]) != SCHEMA_VERSION
        or row["partitions"] != list(SELECTION_PARTITIONS)
        or row["partition_policy"] != "development_and_validation_only"
        or row["input_basis"] != "verified_compact_idea_and_episode_rows"
        or row["archive_record_digests_preverified"] is not True
        or row["representative_join"]
        != "exact_candidate_snapshot_and_episode_identity"
        or row["research_only"] is not True
    ):
        raise ValueError("diagnostic_common_contract_invalid")
    _nat(row["episode_count"])
    _false_fields(
        row,
        "causal_claim model_changed production_policy_claim policy_eligible auto_apply",
    )
    safety = _closed(row["safety"], tuple(_ZERO_SAFETY), "diagnostic_safety")
    if any(type(safety[key]) is not int or safety[key] != 0 for key in _ZERO_SAFETY):
        raise ValueError("diagnostic_safety_nonzero_or_invalid")
    return row


def _validate_bucket_definitions(value: Any) -> None:
    rows = _closed_list(value, len(SCORE_BUCKETS), "score_bucket_definitions")
    if len(rows) != len(SCORE_BUCKETS):
        raise ValueError("score_bucket_definition_count_invalid")
    for row, (label, lower, upper) in zip(rows, SCORE_BUCKETS):
        _closed(row, "name lower_inclusive upper_exclusive".split(), "score_bucket_definition")
        if (
            row["name"] != label
            or _real(row["lower_inclusive"], "bucket_definition_lower") != lower
            or _real(row["upper_exclusive"], "bucket_definition_upper") != upper
        ):
            raise ValueError("score_bucket_definition_invalid")


def _score_groups(
    value: Any, expected: Sequence[tuple[str, ...]], *, partitioned: bool = False
) -> dict[Any, int]:
    groups = _closed_list(value, len(expected), "score_groups")
    if len(groups) != len(expected):
        raise ValueError("score_group_count_invalid")
    output: dict[Any, int] = {}
    for group, identity in zip(groups, expected):
        count = _validate_score_group(group, partitioned=partitioned)
        observed = ((group["partition"],) if partitioned else ()) + (
            group["route"],
            group["conditioning_dimension"],
            group["conditioning_value"],
        )
        if observed != identity:
            raise ValueError("score_group_identity_invalid")
        output[(identity[0], identity[1]) if partitioned else identity[0]] = count
    return output


def _validate_score_group(
    group: Mapping[str, Any], *, partitioned: bool = False
) -> int:
    fields = "route conditioning_dimension conditioning_value episode_count matured_episode_count score_diagnostics descriptive_only policy_eligible auto_apply".split()
    if partitioned:
        fields.insert(0, "partition")
    _closed(group, fields, "score_group")
    if partitioned and group["partition"] not in SELECTION_PARTITIONS:
        raise ValueError("score_group_partition_invalid")
    if (
        group["route"] not in ROUTES
        or not isinstance(group["conditioning_dimension"], str)
        or not isinstance(group["conditioning_value"], str)
        or not group["conditioning_value"]
    ):
        raise ValueError("score_group_identity_invalid")
    episodes = _nat(group["episode_count"])
    matured = _nat(group["matured_episode_count"])
    if matured > episodes or group["descriptive_only"] is not True:
        raise ValueError("score_group_counts_or_mode_invalid")
    _false_fields(group, "policy_eligible auto_apply")
    diagnostics = _closed_list(
        group["score_diagnostics"], len(SCORE_FIELDS), "score_diagnostics"
    )
    if len(diagnostics) != len(SCORE_FIELDS):
        raise ValueError("score_diagnostic_count_invalid")
    for diagnostic, field in zip(diagnostics, SCORE_FIELDS):
        _validate_score_diagnostic(diagnostic, field, episodes, matured)
    return episodes


def _validate_score_diagnostic(
    row: Mapping[str, Any], field: str, episodes: int, matured: int
) -> None:
    fields = "score_field expected_relationship buckets adjacent_comparisons evaluated_adjacent_pair_count violation_count interpretation probabilistic_calibration_claim model_changed policy_eligible auto_apply".split()
    _closed(row, fields, "score_diagnostic")
    expected = SCORE_EXPECTATIONS[field]
    if (
        row["score_field"] != field
        or row["expected_relationship"] != expected
        or row["interpretation"] != "descriptive_route_conditioned_unadjusted"
    ):
        raise ValueError("score_diagnostic_fixed_values_invalid")
    _false_fields(
        row,
        "probabilistic_calibration_claim model_changed policy_eligible auto_apply",
    )
    buckets = _closed_list(row["buckets"], len(SCORE_BUCKETS), "score_buckets")
    if len(buckets) != len(SCORE_BUCKETS):
        raise ValueError("score_bucket_count_invalid")
    observed_episodes = 0
    observed_matured = 0
    for bucket, definition in zip(buckets, SCORE_BUCKETS):
        bucket_episodes, bucket_matured = _validate_score_bucket(bucket, definition)
        observed_episodes += bucket_episodes
        observed_matured += bucket_matured
    if observed_episodes != episodes or observed_matured != matured:
        raise ValueError("score_bucket_count_reconciliation_invalid")
    comparisons = _closed_list(
        row["adjacent_comparisons"], len(SCORE_BUCKETS) - 1, "adjacent_comparisons"
    )
    if len(comparisons) != len(SCORE_BUCKETS) - 1:
        raise ValueError("adjacent_comparison_count_invalid")
    for comparison, lower, higher in zip(comparisons, buckets, buckets[1:]):
        _validate_adjacent_comparison(comparison, lower, higher, expected)
    evaluated = sum(item["evaluation_status"] == "evaluated" for item in comparisons)
    violations = sum(item["violation"] is True for item in comparisons)
    if (
        _nat(row["evaluated_adjacent_pair_count"]) != evaluated
        or _nat(row["violation_count"]) != violations
    ):
        raise ValueError("adjacent_comparison_reconciliation_invalid")


def _validate_score_bucket(
    row: Mapping[str, Any], definition: tuple[str, float, float]
) -> tuple[int, int]:
    fields = "score_bucket lower_inclusive upper_exclusive episode_count matured_episode_count matured_sample_size sample_status evidence_strength cohort_directional_minimum_met mean_directional_return_fraction median_directional_return_fraction hit_rate policy_eligible".split()
    _closed(row, fields, "score_bucket")
    label, lower, upper = definition
    if (
        row["score_bucket"] != label
        or _real(row["lower_inclusive"], "bucket_lower") != lower
        or _real(row["upper_exclusive"], "bucket_upper") != upper
    ):
        raise ValueError("score_bucket_bounds_invalid")
    episodes = _nat(row["episode_count"])
    matured = _nat(row["matured_episode_count"])
    sample = _nat(row["matured_sample_size"])
    status, strength = _sample_status(sample, 5, 30)
    if (
        sample > matured
        or matured > episodes
        or row["sample_status"] != status
        or row["evidence_strength"] != strength
        or row["cohort_directional_minimum_met"] is not (sample >= 30)
        or row["policy_eligible"] is not False
    ):
        raise ValueError("score_bucket_counts_or_status_invalid")
    metrics = [
        row["mean_directional_return_fraction"],
        row["median_directional_return_fraction"],
        row["hit_rate"],
    ]
    if sample == 0:
        if metrics != [None, None, None]:
            raise ValueError("score_bucket_empty_metrics_invalid")
    else:
        _real(metrics[0], "bucket_mean")
        _real(metrics[1], "bucket_median")
        hit = _real(metrics[2], "bucket_hit_rate")
        if not 0.0 <= hit <= 1.0:
            raise ValueError("score_bucket_hit_rate_invalid")
    return episodes, matured


def _validate_adjacent_comparison(
    row: Mapping[str, Any],
    lower: Mapping[str, Any],
    higher: Mapping[str, Any],
    expected: str,
) -> None:
    fields = "lower_bucket higher_bucket lower_matured_sample_size higher_matured_sample_size minimum_matured_sample_size_each evaluation_status observed_delta_fraction expected_relationship violation statistical_significance_claim".split()
    _closed(row, fields, "adjacent_comparison")
    lower_size = _nat(lower["matured_sample_size"])
    higher_size = _nat(higher["matured_sample_size"])
    fixed = (
        row["lower_bucket"] == lower["score_bucket"]
        and row["higher_bucket"] == higher["score_bucket"]
        and _nat(row["lower_matured_sample_size"]) == lower_size
        and _nat(row["higher_matured_sample_size"]) == higher_size
        and _nat(row["minimum_matured_sample_size_each"]) == 5
        and row["expected_relationship"] == expected
        and row["statistical_significance_claim"] is False
    )
    eligible = lower_size >= 5 and higher_size >= 5
    delta = (
        round(
            float(higher["mean_directional_return_fraction"])
            - float(lower["mean_directional_return_fraction"]),
            12,
        )
        if eligible
        else None
    )
    violation = (
        (delta < 0.0 if expected.startswith("nondecreasing") else delta > 0.0)
        if eligible
        else None
    )
    observed_delta = _real_or_none(row["observed_delta_fraction"], "adjacent_delta")
    if (
        not fixed
        or row["evaluation_status"]
        != ("evaluated" if eligible else "insufficient_sample")
        or observed_delta != delta
        or row["violation"] is not violation
    ):
        raise ValueError("adjacent_comparison_invalid")


def _validate_composition(
    row: Mapping[str, Any], route_totals: Mapping[str, int]
) -> None:
    composition = _closed_list(
        row["between_route_bucket_composition"],
        len(SCORE_FIELDS) * len(SCORE_BUCKETS),
        "route_composition",
    )
    expected_pairs = [
        (field, bucket[0]) for field in SCORE_FIELDS for bucket in SCORE_BUCKETS
    ]
    if len(composition) != len(expected_pairs):
        raise ValueError("route_composition_count_invalid")
    per_field: Counter[str] = Counter()
    per_field_route: Counter[tuple[str, str]] = Counter()
    for item, pair in zip(composition, expected_pairs):
        _closed(
            item,
            "score_field score_bucket episode_count routes route_counts_reconcile".split(),
            "route_composition_row",
        )
        if (item["score_field"], item["score_bucket"]) != pair:
            raise ValueError("route_composition_identity_invalid")
        total = _nat(item["episode_count"])
        route_rows = _closed_list(item["routes"], len(ROUTES), "composition_routes")
        if len(route_rows) != len(ROUTES):
            raise ValueError("composition_route_count_invalid")
        observed = 0
        for route_row, route in zip(route_rows, ROUTES):
            _closed(
                route_row,
                "route episode_count share_of_score_bucket share_of_route".split(),
                "composition_route",
            )
            count = _nat(route_row["episode_count"])
            observed += count
            bucket_share = _real_or_none(
                route_row["share_of_score_bucket"], "composition_bucket_share"
            )
            route_share = _real_or_none(
                route_row["share_of_route"], "composition_route_share"
            )
            if (
                route_row["route"] != route
                or bucket_share != (round(count / total, 12) if total else None)
                or route_share
                != (
                    round(count / route_totals[route], 12)
                    if route_totals[route]
                    else None
                )
            ):
                raise ValueError("composition_route_reconciliation_invalid")
            per_field_route[(str(item["score_field"]), route)] += count
        if observed != total or item["route_counts_reconcile"] is not True:
            raise ValueError("route_composition_reconciliation_invalid")
        per_field[str(item["score_field"])] += total
    if any(
        per_field_route[(field, route)] != route_totals[route]
        for field in SCORE_FIELDS
        for route in ROUTES
    ):
        raise ValueError("composition_route_totals_invalid")
    _validate_composition_summary(row, route_totals, per_field)


def _validate_composition_summary(
    row: Mapping[str, Any],
    route_totals: Mapping[str, int],
    per_field: Mapping[str, int],
) -> None:
    total = sum(route_totals.values())
    reconciliation = _closed(
        row["composition_reconciliation"],
        "per_score_field all_score_fields_reconcile all_route_counts_reconcile".split(),
        "composition_reconciliation",
    )
    summaries = _closed_list(
        reconciliation["per_score_field"],
        len(SCORE_FIELDS),
        "composition_field_summaries",
    )
    valid = len(summaries) == len(SCORE_FIELDS)
    for summary, field in zip(summaries, SCORE_FIELDS):
        _closed(
            summary,
            "score_field expected_episode_count bucket_membership_count reconciles".split(),
            "composition_field_summary",
        )
        valid = (
            valid
            and summary["score_field"] == field
            and _nat(summary["expected_episode_count"]) == total
            and _nat(summary["bucket_membership_count"]) == total
            and summary["reconciles"] is True
        )
    if (
        not valid
        or reconciliation["all_score_fields_reconcile"] is not True
        or reconciliation["all_route_counts_reconcile"] is not True
        or any(per_field[field] != total for field in SCORE_FIELDS)
    ):
        raise ValueError("composition_summary_reconciliation_invalid")


def _validate_affected_asset_lists(value: Any, assets: list[str], distinct: int) -> None:
    rows = _closed_list(value, len(AFFECTED_ASSET_LIMITS), "affected_asset_lists")
    if len(rows) != len(AFFECTED_ASSET_LIMITS):
        raise ValueError("affected_asset_lists_invalid")
    for item, limit in zip(rows, AFFECTED_ASSET_LIMITS):
        _closed(item, "limit assets asset_count truncated".split(), "affected_asset_list")
        expected = assets[:limit]
        if (
            _nat(item["limit"]) != limit
            or item["assets"] != expected
            or _nat(item["asset_count"]) != len(expected)
            or item["truncated"] is not (distinct > limit)
        ):
            raise ValueError("affected_asset_list_reconciliation_invalid")


def _validate_risk_assets(value: Any, partition: str, distinct: int) -> list[str]:
    rows = _closed_list(value, AFFECTED_ASSET_LIMITS[-1], "ranked_asset_evidence")
    if len(rows) != min(distinct, AFFECTED_ASSET_LIMITS[-1]):
        raise ValueError("risk_asset_evidence_count_invalid")
    assets: list[str] = []
    ranks: list[tuple[Any, ...]] = []
    for index, row in enumerate(rows, start=1):
        _closed(
            row,
            "rank canonical_asset_id episode_id candidate_id partition return_24h_fraction volume_zscore_24h liquidity_usd market_regime".split(),
            "risk_asset",
        )
        asset = row["canonical_asset_id"]
        if (
            _nat(row["rank"]) != index
            or not isinstance(asset, str)
            or not asset
            or asset != _token(asset)
            or asset in assets
            or row["partition"] != partition
            or not all(
                isinstance(row[key], str)
                and row[key]
                and (key != "market_regime" or row[key] == _token(row[key]))
                for key in ("episode_id", "candidate_id", "market_regime")
            )
        ):
            raise ValueError("risk_asset_identity_invalid")
        returned = _real_or_none(row["return_24h_fraction"], "risk_asset_return")
        volume = _real_or_none(row["volume_zscore_24h"], "risk_asset_volume")
        liquidity = _real_or_none(row["liquidity_usd"], "risk_asset_liquidity")
        if (
            returned is not None
            and abs(returned) > 3.0
            or liquidity is not None
            and liquidity < 0.0
        ):
            raise ValueError("risk_asset_numeric_bounds_invalid")
        assets.append(asset)
        ranks.append(
            (
                returned is None,
                returned or 0.0,
                volume is None,
                -volume if volume is not None else 0.0,
                liquidity is None,
                -liquidity if liquidity is not None else 0.0,
                asset,
                row["episode_id"],
            )
        )
    if ranks != sorted(ranks):
        raise ValueError("risk_asset_ranking_invalid")
    return assets


def _validate_regime_visibility(
    row: Mapping[str, Any], days: Sequence[Mapping[str, Any]]
) -> None:
    visibility = _closed_list(
        row["regime_conditioned_visibility"], 512, "regime_visibility"
    )
    counts: Counter[str] = Counter()
    partition_days: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for day in days:
        for regime, count in day["market_regime_counts"].items():
            counts[str(regime)] += count
            if count > 0:
                partition_days[str(regime)].add((day["partition"], day["utc_day"]))
    day_counts = Counter(
        {regime: len(identities) for regime, identities in partition_days.items()}
    )
    total = row["risk_item_count"]
    if (
        sum(_validate_regime_row(item, total, counts, day_counts) for item in visibility)
        != total
        or [item["market_regime"] for item in visibility]
        != sorted(set(counts) | {"unknown"})
    ):
        raise ValueError("regime_visibility_reconciliation_invalid")


def _validate_regime_row(
    row: Mapping[str, Any],
    total: int,
    counts: Mapping[str, int],
    days: Mapping[str, int],
) -> int:
    _closed(
        row,
        "market_regime risk_item_count distinct_asset_count observed_day_count share_of_risk_items descriptive_only policy_eligible".split(),
        "regime_visibility",
    )
    regime = row["market_regime"]
    if not isinstance(regime, str) or not regime:
        raise ValueError("regime_visibility_identity_invalid")
    count = _nat(row["risk_item_count"])
    distinct = _nat(row["distinct_asset_count"])
    observed_days = _nat(row["observed_day_count"])
    observed_share = _real_or_none(
        row["share_of_risk_items"], "regime_visibility_share"
    )
    share = round(count / total, 12) if total else None
    if (
        count != counts.get(regime, 0)
        or observed_days != days.get(regime, 0)
        or distinct > count
        or observed_days > count
        or observed_share != share
        or row["descriptive_only"] is not True
        or row["policy_eligible"] is not False
    ):
        raise ValueError("regime_visibility_values_invalid")
    return count


def _sample_status(
    count: int, descriptive_minimum: int, cohort_minimum: int
) -> tuple[str, str]:
    if count == 0:
        return "no_sample", "no_evidence"
    if count < descriptive_minimum:
        return "insufficient_sample", "insufficient"
    if count < cohort_minimum:
        return "insufficient_exploratory", "exploratory_below_cohort_minimum"
    return "cohort_directional_sample", "cohort_directional"


def _protocol() -> Mapping[str, Any]:
    protocol = empirical_validation_protocol.protocol_values()
    errors = empirical_validation_protocol.validate_protocol(protocol)
    if errors:
        raise ValueError("diagnostic_frozen_protocol_invalid:" + ";".join(errors))
    return protocol


def _closed(value: Any, fields: Sequence[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(fields):
        raise ValueError(f"{label}_fields_invalid")
    return value


def _closed_list(value: Any, maximum: int, label: str) -> list[Mapping[str, Any]]:
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or any(not isinstance(item, Mapping) for item in value)
    ):
        raise ValueError(f"{label}_invalid")
    return value


def _false_fields(value: Mapping[str, Any], fields: str) -> None:
    if any(value.get(field) is not False for field in fields.split()):
        raise ValueError("diagnostic_false_flag_invalid")


def _nat(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("diagnostic_natural_number_invalid")
    return value


def _real(value: Any, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label}_invalid")
    return float(value)


def _real_or_none(value: Any, label: str) -> float | None:
    return None if value is None else _real(value, label)


def _fingerprint(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX for character in value)
    ):
        raise ValueError("diagnostic_source_run_fingerprint_invalid")
    return value


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(empirical_replay_store.canonical_json_bytes(value)).hexdigest()


def _token(value: Any) -> str:
    return str(value).strip().casefold() if value not in (None, "") else ""


def _utc_day(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("diagnostic_observed_at_required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("diagnostic_observed_at_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("diagnostic_observed_at_timezone_required")
    return parsed.astimezone(timezone.utc).date().isoformat()


__all__ = [
    "AFFECTED_ASSET_LIMITS",
    "CONDITIONING_DIMENSIONS",
    "CORRELATED_FAMILY_STATUS",
    "MARKET_RISK_SCHEMA_ID",
    "ROUTE_CALIBRATION_SCHEMA_ID",
    "SCHEMA_VERSION",
    "SELECTION_PARTITIONS",
    "validate_market_wide_risk_diagnostics",
    "validate_route_conditioned_calibration",
]
