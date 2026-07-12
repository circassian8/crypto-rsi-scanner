"""Outcome Checks for the artifact doctor."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone

from ...outcomes import outcome_eligibility as outcome_eligibility_contract
from .runtime import *
from .integrated_radar_checks import (
    _safe_float,
    _structured_operator_path_conflict_count,
)


_OUTCOME_PROVENANCE_FAILURE_REASONS = frozenset({
    "duplicate_horizon_price_observation_id",
    "horizon_exit_price_invalid",
    "horizon_exit_price_missing",
    "horizon_metadata_contract_invalid",
    "horizon_price_lineage_contract_invalid",
    "horizon_price_observation_id_missing",
    "horizon_price_source_missing",
    "horizon_return_contract_invalid",
    "horizon_return_recompute_mismatch",
    "invalid_observation_price",
    "missing_observation_price",
    "missing_observation_price_id",
    "missing_observation_price_observed_at",
    "missing_observation_price_provenance",
    "missing_observation_price_source",
    "missing_outcome_evaluated_at",
    "missing_primary_horizon",
    "missing_primary_horizon_metadata",
    "observation_price_after_candidate",
    "observation_price_after_evaluation",
    "observation_price_stale",
    "primary_horizon_due_in_future",
    "primary_horizon_due_mismatch",
    "primary_horizon_lane_mismatch",
    "primary_horizon_missing_due_at",
    "primary_horizon_missing_price_observed_at",
    "primary_horizon_missing_provenance",
    "primary_horizon_not_mature",
    "primary_horizon_pending",
    "primary_horizon_price_after_evaluation",
    "primary_horizon_price_before_due",
    "primary_horizon_price_lag_exceeded",
    "primary_horizon_return_invalid",
    "primary_horizon_return_mismatch",
})
_NON_AUTHORITATIVE_OUTCOME_LABELS = frozenset({
    "",
    "inconclusive",
    "missing_data",
    "not_applicable",
    "pending",
    "synthetic_fixture",
    "unknown",
    "unvalidated",
})


def _joined_authority_invalid_identities(
    outcomes: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    core_rows: Iterable[Mapping[str, Any]] | None,
    *,
    evaluated_at: Any,
) -> set[tuple[str, ...]]:
    if core_rows is None:
        return set()
    _eligible, excluded, _reasons = (
        outcome_eligibility_contract.partition_joined_calibration_outcomes(
            outcomes,
            candidates,
            core_rows,
            evaluated_at=evaluated_at,
        )
    )
    authority_reasons = {
        "ambiguous_outcome_identity",
        "candidate_authority_contract_invalid",
        "core_authority_contract_invalid",
        "core_authority_generated_in_future",
        "identity_mismatch",
        "unmatched_outcome_identity",
    }
    return {
        identity
        for row in excluded
        if authority_reasons & set(row.get("calibration_ineligible_reasons") or ())
        and (
            identity := outcome_eligibility_contract.canonical_join_identity(row)
        )
        is not None
    }

def _integrated_delivery_conflicts(
    rows: Iterable[Mapping[str, Any]],
    *,
    preview_path: str | Path | None,
) -> dict[str, int]:
    out = {
        "integrated_preview_lane_mismatch": 0,
        "integrated_delivery_missing_disclaimer": 0,
        "integrated_delivery_sent_in_no_send": 0,
        "integrated_delivery_side_effect_flag": 0,
        "integrated_delivery_missing_skip_reasons": 0,
        "integrated_delivery_card_path_absolute": 0,
        "integrated_delivery_card_path_not_rendered": 0,
        "integrated_operator_markdown_absolute_path": 0,
        "operator_structured_path_absolute": 0,
    }
    materialized = [dict(row) for row in rows if isinstance(row, Mapping)]
    preview_text = ""
    if preview_path is not None:
        try:
            preview_text = Path(preview_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            preview_text = ""
    preview_missing = preview_path is not None and not preview_text
    for row in materialized:
        message = str(row.get("message_text") or "")
        if "Research-only" not in message or "Not a trade signal" not in message:
            out["integrated_delivery_missing_disclaimer"] += 1
        if row.get("sent") and row.get("no_send_rehearsal"):
            out["integrated_delivery_sent_in_no_send"] += 1
        for key in ("normal_rsi_signal_written", "triggered_fade_created", "paper_trade_created", "trade_created"):
            if _truthy(row.get(key)):
                out["integrated_delivery_side_effect_flag"] += 1
        if int(row.get("skipped_item_count") or 0) > 0 and not row.get("skipped_items"):
            out["integrated_delivery_missing_skip_reasons"] += 1
        if event_artifact_paths.has_operator_absolute_path(row.get("card_paths") or ()):
            out["integrated_delivery_card_path_absolute"] += 1
        card_paths = [str(item) for item in _tuple_value(row.get("card_paths")) if str(item).strip()]
        if card_paths:
            if "Card: none" in message:
                out["integrated_delivery_card_path_not_rendered"] += 1
            elif not any(path in message or Path(path).name in message for path in card_paths):
                out["integrated_delivery_card_path_not_rendered"] += 1
        if event_artifact_paths.has_operator_absolute_path(message):
            out["integrated_operator_markdown_absolute_path"] += 1
        out["operator_structured_path_absolute"] += _structured_operator_path_conflicts((row,))
        lane_title = str(row.get("lane_title") or "")
        rendered_items = _int(row.get("rendered_item_count"))
        if preview_missing and rendered_items > 0:
            out["integrated_preview_lane_mismatch"] += 1
            continue
        if preview_text and lane_title and lane_title not in preview_text:
            out["integrated_preview_lane_mismatch"] += 1
    return out

def _int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0

def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "on"}
    return bool(value)

def _tuple_value(value: object) -> tuple[object, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, set):
        return tuple(sorted(value, key=str))
    return (value,)


def _materialize_outcome_conflict_authority(
    candidates: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]] | None,
    evaluated_at: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Any, set[tuple[str, ...]]]:
    outcome_rows = [dict(row) for row in outcomes if isinstance(row, Mapping)]
    candidate_rows = [dict(row) for row in candidates if isinstance(row, Mapping)]
    evaluation_clock = (
        evaluated_at if evaluated_at is not None else datetime.now(timezone.utc)
    )
    invalid_identities = _joined_authority_invalid_identities(
        outcome_rows,
        candidate_rows,
        core_rows,
        evaluated_at=evaluation_clock,
    )
    return outcome_rows, candidate_rows, evaluation_clock, invalid_identities


def _integrated_outcome_conflicts(
    candidates: Iterable[Mapping[str, Any]],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    core_rows: Iterable[Mapping[str, Any]] | None = None,
    evaluated_at: Any = None,
) -> dict[str, int]:
    out = {
        "integrated_outcome_missing_for_candidate": 0,
        "integrated_outcome_side_effect_flag": 0,
        "integrated_outcome_schema_missing": 0,
        "integrated_outcome_missing_identity": 0,
        "integrated_outcome_returns_without_price": 0,
        "integrated_outcome_diagnostic_in_performance": 0,
        "integrated_outcome_return_double_scaled": 0,
        "integrated_outcome_missing_data_unlabeled": 0,
        "integrated_outcome_thesis_move_missing": 0,
        "integrated_outcome_eligibility_contract_invalid": 0,
        "integrated_outcome_synthetic_evidence_leak": 0,
        "integrated_outcome_immature_validation_claim": 0,
        "integrated_outcome_duplicate_exact_identity": 0,
        "integrated_outcome_ambiguous_exact_identity": 0,
        "integrated_outcome_eligible_provenance_missing": 0,
        "integrated_outcome_identity_mismatch": 0,
    }
    outcome_rows, candidate_rows, evaluation_clock, authority_invalid_identities = (
        _materialize_outcome_conflict_authority(
            candidates, outcomes, core_rows, evaluated_at
        )
    )
    exact_identity_keys: list[str] = []
    candidate_identity_counts: Counter[str] = Counter()
    for candidate in candidate_rows:
        candidate_identity = outcome_eligibility_contract.canonical_outcome_identity(candidate)
        if outcome_eligibility_contract.canonical_join_identity(candidate) is not None:
            candidate_identity_counts[
                outcome_eligibility_contract.canonical_outcome_identity_key(candidate_identity)
            ] += 1
    for row in outcome_rows:
        if not outcome_eligibility_contract.has_outcome_eligibility_marker(row):
            continue
        identity = outcome_eligibility_contract.canonical_outcome_identity(row)
        if outcome_eligibility_contract.canonical_join_identity(row) is None:
            continue
        identity_key = outcome_eligibility_contract.canonical_outcome_identity_key(identity)
        exact_identity_keys.append(identity_key)
    identity_counts = Counter(exact_identity_keys)
    out["integrated_outcome_duplicate_exact_identity"] = sum(
        count - 1 for count in identity_counts.values() if count > 1
    )
    out["integrated_outcome_ambiguous_exact_identity"] = sum(
        1
        for row in outcome_rows
        if outcome_eligibility_contract.has_outcome_eligibility_marker(row)
        and _outcome_identity_is_ambiguous(row, candidate_identity_counts)
    )
    candidates_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidate_rows:
        candidate_id = str(candidate.get("candidate_id") or "").strip()
        if candidate_id:
            candidates_by_id[candidate_id].append(candidate)
    outcome_by_candidate = {str(row.get("candidate_id") or ""): row for row in outcome_rows if row.get("candidate_id")}
    for candidate in candidate_rows:
        if str(candidate.get("opportunity_type") or "") == "DIAGNOSTIC":
            continue
        if str(candidate.get("candidate_id") or "") not in outcome_by_candidate:
            out["integrated_outcome_missing_for_candidate"] += 1
    for row in outcome_rows:
        _update_outcome_eligibility_conflicts(
            out,
            row,
            candidates_by_id,
            joined_authority_invalid=(
                outcome_eligibility_contract.canonical_join_identity(row)
                in authority_invalid_identities
            ),
            evaluated_at=evaluation_clock,
        )
        for key in ("normal_rsi_signal_written", "triggered_fade_created", "paper_trade_created", "trade_created"):
            if _truthy(row.get(key)):
                out["integrated_outcome_side_effect_flag"] += 1
        if (
            not outcome_eligibility_contract.has_outcome_eligibility_marker(row)
            and (
                not _truthy(row.get("no_trade_created"))
                or not _truthy(row.get("no_paper_trade_created"))
            )
        ):
            out["integrated_outcome_schema_missing"] += 1
        if not (row.get("symbol") and row.get("coin_id")):
            out["integrated_outcome_missing_identity"] += 1
        if (
            row.get("primary_horizon_return") is not None
            and row.get("price_at_observation") in (None, "")
            and row.get("outcome_data_source") != "synthetic_fixture"
        ):
            out["integrated_outcome_returns_without_price"] += 1
        if str(row.get("opportunity_type") or "") == "DIAGNOSTIC" and _truthy(row.get("include_in_performance")):
            out["integrated_outcome_diagnostic_in_performance"] += 1
        returns = [row.get("primary_horizon_return")]
        horizons = row.get("horizons")
        if isinstance(horizons, Mapping):
            returns.extend(horizons.values())
        if str(row.get("outcome_status") or "").casefold() in {"filled", "partial"}:
            if not _tuple_value(row.get("outcome_horizons")):
                out["integrated_outcome_schema_missing"] += 1
            required_mappings = (
                "return_by_horizon",
                "relative_return_vs_btc_by_horizon",
                "relative_return_vs_eth_by_horizon",
                "max_favorable_excursion_by_window",
                "max_adverse_excursion_by_window",
            )
            for key in required_mappings:
                if not isinstance(row.get(key), Mapping):
                    out["integrated_outcome_schema_missing"] += 1
                    break
            thesis_required_mappings = (
                "thesis_return_by_horizon",
                "thesis_relative_return_vs_btc_by_horizon",
                "thesis_favorable_excursion_by_window",
                "thesis_adverse_excursion_by_window",
            )
            for key in thesis_required_mappings:
                if not isinstance(row.get(key), Mapping):
                    out["integrated_outcome_schema_missing"] += 1
                    break
            if not str(row.get("thesis_direction") or "").strip() or not str(
                row.get("thesis_outcome_interpretation") or ""
            ).strip():
                out["integrated_outcome_schema_missing"] += 1
            if not (
                row.get("benchmark_btc_price_at_observation") is not None
                or row.get("benchmark_eth_price_at_observation") is not None
            ):
                out["integrated_outcome_schema_missing"] += 1
        lane = str(row.get("opportunity_type") or "").upper()
        label = str(row.get("outcome_label") or "")
        thesis_primary = _safe_float(row.get("thesis_primary_move"))
        if lane == "FADE_SHORT_REVIEW" and label in {"fade_review_good", "useful"}:
            if thesis_primary is None or thesis_primary <= 0:
                out["integrated_outcome_thesis_move_missing"] += 1
        if lane == "RISK_ONLY" and label in {"risk_validated", "useful"}:
            if thesis_primary is None or thesis_primary <= 0:
                out["integrated_outcome_thesis_move_missing"] += 1
        if any(isinstance(value, (int, float)) and abs(float(value)) > 5.0 for value in returns):
            out["integrated_outcome_return_double_scaled"] += 1
        if str(row.get("outcome_status") or "") == "missing_data" and not row.get("missing_data_reason"):
            out["integrated_outcome_missing_data_unlabeled"] += 1
    return out


def _update_outcome_eligibility_conflicts(
    out: dict[str, int],
    row: Mapping[str, Any],
    candidates_by_id: Mapping[str, list[dict[str, Any]]],
    *,
    joined_authority_invalid: bool = False,
    evaluated_at: Any,
) -> None:
    has_firewall = outcome_eligibility_contract.has_outcome_eligibility_marker(row)
    contract_errors = outcome_eligibility_contract.validate_contract(row) if has_firewall else ()
    contract_invalid = bool(contract_errors) or joined_authority_invalid
    effective_eligible, effective_reasons = (
        outcome_eligibility_contract.effective_calibration_state(
            row,
            evaluated_at=evaluated_at,
        )
    )
    reasons = set(effective_reasons)
    if row.get("calibration_eligible") is True and not effective_eligible:
        contract_invalid = True
    if contract_invalid:
        out["integrated_outcome_eligibility_contract_invalid"] += 1
    if row.get("outcome_data_source") == "synthetic_fixture" and (
        row.get("calibration_eligible") is True
        or _truthy(row.get("include_in_performance"))
        or _authoritative_outcome_claim(row)
    ):
        out["integrated_outcome_synthetic_evidence_leak"] += 1
    immature_reasons = {
        "horizon_metadata_contract_invalid",
        "missing_outcome_evaluated_at",
        "missing_primary_horizon",
        "missing_primary_horizon_metadata",
        "primary_horizon_due_in_future",
        "primary_horizon_due_mismatch",
        "primary_horizon_missing_due_at",
        "primary_horizon_missing_price_observed_at",
        "primary_horizon_not_mature",
        "primary_horizon_pending",
        "primary_horizon_price_after_evaluation",
        "primary_horizon_price_before_due",
        "primary_horizon_price_lag_exceeded",
    }
    if _authoritative_outcome_claim(row) and reasons & immature_reasons:
        out["integrated_outcome_immature_validation_claim"] += 1
    if row.get("calibration_eligible") is True and reasons & _OUTCOME_PROVENANCE_FAILURE_REASONS:
        out["integrated_outcome_eligible_provenance_missing"] += 1
    if has_firewall and _outcome_identity_mismatches_candidates(row, candidates_by_id):
        out["integrated_outcome_identity_mismatch"] += 1


def _authoritative_outcome_claim(row: Mapping[str, Any]) -> bool:
    if row.get("calibration_eligible") is True or _truthy(row.get("include_in_performance")):
        return True
    for field in ("validation_label", "outcome_label"):
        label = str(row.get(field) or "").strip().casefold()
        if label not in _NON_AUTHORITATIVE_OUTCOME_LABELS:
            return True
    return False


def _outcome_identity_mismatches_candidates(
    row: Mapping[str, Any],
    candidates_by_id: Mapping[str, list[dict[str, Any]]],
) -> bool:
    identity = outcome_eligibility_contract.canonical_outcome_identity(row)
    if outcome_eligibility_contract.canonical_join_identity(row) is None:
        return True
    candidate_rows = candidates_by_id.get(identity["candidate_id"], ())
    if not candidate_rows:
        return True
    for candidate in candidate_rows:
        if all(
            isinstance(candidate.get(field), str)
            and bool(str(candidate.get(field)).strip())
            and str(candidate.get(field)) == identity[field]
            for field in outcome_eligibility_contract.OUTCOME_IDENTITY_FIELDS
        ):
            return False
    return True


def _outcome_identity_is_ambiguous(
    row: Mapping[str, Any],
    candidate_identity_counts: Mapping[str, int],
) -> bool:
    identity = outcome_eligibility_contract.canonical_outcome_identity(row)
    nested = row.get("outcome_identity")
    if outcome_eligibility_contract.canonical_join_identity(row) is None or not isinstance(nested, Mapping):
        return True
    if set(nested) != set(outcome_eligibility_contract.OUTCOME_IDENTITY_FIELDS):
        return True
    if any(nested.get(field) != identity[field] for field in outcome_eligibility_contract.OUTCOME_IDENTITY_FIELDS):
        return True
    identity_key = outcome_eligibility_contract.canonical_outcome_identity_key(identity)
    if row.get("outcome_identity_key") != identity_key:
        return True
    return int(candidate_identity_counts.get(identity_key, 0)) > 1

def _integrated_calibration_conflicts(path: str | Path | None) -> dict[str, int]:
    out = {
        "integrated_calibration_diagnostic_in_main_priors": 0,
        "integrated_calibration_prior_safety_missing": 0,
        "integrated_calibration_api_alias_top_level": 0,
    }
    if path is None or not Path(path).exists():
        return out
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return out
    if not isinstance(data, Mapping):
        return out
    priors = data.get("opportunity_type_priors")
    if not isinstance(priors, Mapping):
        return out
    if "DIAGNOSTIC" in {str(key).upper() for key in priors}:
        out["integrated_calibration_diagnostic_in_main_priors"] += 1
    if not _truthy(data.get("recommendation_only")) or _truthy(data.get("auto_apply")) or _truthy(data.get("eligible_for_auto_apply")):
        out["integrated_calibration_prior_safety_missing"] += 1
    for value in priors.values():
        if not isinstance(value, Mapping):
            out["integrated_calibration_prior_safety_missing"] += 1
            continue
        if ("useful" in value or "junk" in value) and not isinstance(value.get("legacy_aliases"), Mapping):
            out["integrated_calibration_api_alias_top_level"] += 1
        sample_size = _safe_float(value.get("sample_size"))
        min_sample_size = _safe_float(value.get("min_sample_size"))
        has_warning = bool(str(value.get("min_sample_warning") or "").strip())
        if (
            sample_size is None
            or min_sample_size is None
            or value.get("confidence") in (None, "")
            or not _truthy(value.get("recommendation_only"))
            or _truthy(value.get("eligible_for_auto_apply"))
            or _truthy(value.get("auto_apply"))
            or not str(value.get("excluded_from_auto_apply_reason") or "").strip()
            or not str(value.get("last_updated_at") or "").strip()
            or not str(value.get("horizon_basis") or "").strip()
        ):
            out["integrated_calibration_prior_safety_missing"] += 1
            continue
        if sample_size < min_sample_size and not has_warning:
            out["integrated_calibration_prior_safety_missing"] += 1
    return out

def _integrated_performance_dashboard_conflicts(namespace_dir: str | Path | None) -> dict[str, int]:
    out = {
        "integrated_performance_diagnostic_in_main_aggregate": 0,
        "integrated_performance_auto_apply_enabled": 0,
        "integrated_performance_low_sample_missing_warning": 0,
        "integrated_performance_trade_pnl_wording": 0,
    }
    if namespace_dir is None:
        return out
    base = Path(namespace_dir)
    json_path = base / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME
    dashboard_path = base / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME
    data: Any = None
    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
    if isinstance(data, Mapping):
        if _performance_main_sections_contain_diagnostic(data):
            out["integrated_performance_diagnostic_in_main_aggregate"] += 1
        out["integrated_performance_auto_apply_enabled"] += _performance_auto_apply_enabled(data)
        out["integrated_performance_low_sample_missing_warning"] += _performance_low_sample_missing_warning(data)
    combined_text = ""
    for path in (json_path, dashboard_path):
        if not path.exists():
            continue
        try:
            combined_text += "\n" + path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    if re.search(r"\b(trade|trades|trading|paper|pnl|p&l|profit|loss)\b", combined_text, flags=re.IGNORECASE):
        out["integrated_performance_trade_pnl_wording"] += 1
    return out

def _performance_main_sections_contain_diagnostic(data: Mapping[str, Any]) -> bool:
    lane_summaries = data.get("lane_summaries")
    if _contains_diagnostic_value(lane_summaries):
        return True
    for section in (
        data.get("main_aggregate"),
        data.get("performance_views"),
        data.get("provider_performance"),
    ):
        if _contains_named_diagnostic_route(section):
            return True
    dimensions = data.get("dimension_summaries")
    if not isinstance(dimensions, Mapping):
        return False
    return any(
        _contains_diagnostic_value(dimensions.get(field))
        for field in ("opportunity_type", "radar_route")
    )

def _contains_named_diagnostic_route(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).strip().casefold() in {"opportunity_type", "radar_route"}:
                if _contains_diagnostic_value(nested):
                    return True
            elif _contains_named_diagnostic_route(nested):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_contains_named_diagnostic_route(item) for item in value)
    return False

def _contains_diagnostic_value(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key).strip().upper() == "DIAGNOSTIC":
                return True
            if _contains_diagnostic_value(nested):
                return True
    elif isinstance(value, (list, tuple, set)):
        return any(_contains_diagnostic_value(item) for item in value)
    elif str(value).strip().upper() == "DIAGNOSTIC":
        return True
    return False

def _performance_auto_apply_enabled(value: Any) -> int:
    count = 0
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in {"auto_apply", "eligible_for_auto_apply"} and _truthy(nested):
                count += 1
            count += _performance_auto_apply_enabled(nested)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            count += _performance_auto_apply_enabled(item)
    return count

def _performance_low_sample_missing_warning(value: Any) -> int:
    count = 0
    if isinstance(value, Mapping):
        sample = _safe_float(value.get("sample_size"))
        min_sample = _safe_float(value.get("min_sample_size"))
        if sample is not None and min_sample is not None and sample < min_sample and not _truthy(value.get("min_sample_warning")):
            count += 1
        for nested in value.values():
            count += _performance_low_sample_missing_warning(nested)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            count += _performance_low_sample_missing_warning(item)
    return count

def _structured_operator_path_conflicts(rows: Iterable[Mapping[str, Any]]) -> int:
    conflicts = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        conflicts += _structured_operator_path_conflict_count(row)
    return conflicts

__all__ = (
    '_integrated_delivery_conflicts',
    '_integrated_outcome_conflicts',
    '_integrated_calibration_conflicts',
    '_integrated_performance_dashboard_conflicts',
    '_performance_main_sections_contain_diagnostic',
    '_contains_diagnostic_value',
    '_performance_auto_apply_enabled',
    '_performance_low_sample_missing_warning',
    '_structured_operator_path_conflicts',
)
