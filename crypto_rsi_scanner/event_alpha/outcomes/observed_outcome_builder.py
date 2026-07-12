"""Pure offline builder for provenance-complete observed-market outcomes."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping

from . import outcome_eligibility


OBSERVED_OUTCOME_BUILD_ERRORS = frozenset(
    {
        "ambiguous_close_timestamp",
        "candidate_asset_identity_invalid",
        "candidate_authority_contract_invalid",
        "candidate_authority_count_invalid",
        "candidate_core_attribution_mismatch",
        "candidate_observed_after_evaluation",
        "core_authority_contract_invalid",
        "core_authority_count_invalid",
        "core_authority_generated_after_evaluation",
        "duplicate_close_observation_id",
        "entry_price_missing",
        "entry_price_stale",
        "invalid_close_observation",
        "invalid_evaluated_at",
        "invalid_price_data_kind",
        "invalid_primary_horizon_lane",
        "price_observations_missing",
        "synthetic_lineage_claimed_observed",
    }
)


@dataclass(frozen=True)
class _ObservedClose:
    symbol: str
    coin_id: str
    close_observed_at: datetime
    close: float
    source: str
    observation_id: str


@dataclass(frozen=True)
class _ObservedOutcomeBuildResult:
    outcome: dict[str, Any] | None
    build_errors: tuple[str, ...]
    observations_supplied: int
    observations_accepted: int

    @property
    def produced(self) -> bool:
        return self.outcome is not None


def build_observed_outcome(
    candidate_rows: Iterable[Mapping[str, Any]],
    core_rows: Iterable[Mapping[str, Any]],
    close_rows: Iterable[Mapping[str, Any]],
    *,
    evaluated_at: Any,
    price_data_kind: str = "synthetic_fixture",
) -> _ObservedOutcomeBuildResult:
    """Build one offline outcome from exact authority and completed closes.

    The function is intentionally pure: it performs no I/O, network calls,
    persistence, notification, paper-trade, signal, or execution work.
    """

    candidates = [dict(row) for row in candidate_rows if isinstance(row, Mapping)]
    cores = [dict(row) for row in core_rows if isinstance(row, Mapping)]
    supplied_closes = [dict(row) for row in close_rows if isinstance(row, Mapping)]
    evaluation = outcome_eligibility.parse_aware_time(evaluated_at)
    errors: set[str] = set()
    if evaluation is None:
        errors.add("invalid_evaluated_at")
    if price_data_kind not in {"observed_market_prices", "synthetic_fixture"}:
        errors.add("invalid_price_data_kind")
    if len(candidates) != 1:
        errors.add("candidate_authority_count_invalid")
    if errors:
        return _result(None, errors, supplied_closes, ())

    candidate = candidates[0]
    if not outcome_eligibility.valid_candidate_authority(candidate):
        errors.add("candidate_authority_contract_invalid")
    candidate_observed = outcome_eligibility.parse_aware_time(candidate.get("observed_at"))
    if candidate_observed is None:
        errors.add("candidate_authority_contract_invalid")
    elif evaluation is not None and candidate_observed > evaluation:
        errors.add("candidate_observed_after_evaluation")
    symbol = candidate.get("symbol")
    coin_id = candidate.get("coin_id")
    if not _canonical_text(symbol) or not _canonical_text(coin_id):
        errors.add("candidate_asset_identity_invalid")
    primary_horizon = outcome_eligibility.primary_horizon_for_lane(
        candidate.get("opportunity_type")
    )
    if primary_horizon is None:
        errors.add("invalid_primary_horizon_lane")

    matching_cores = [
        core
        for core in cores
        if _core_context(core) is not None
        and _core_context(core) == _core_context(candidate)
    ]
    if len(matching_cores) != 1:
        errors.add("core_authority_count_invalid")
        core = None
    else:
        core = matching_cores[0]
        if not outcome_eligibility.valid_core_authority(core):
            errors.add("core_authority_contract_invalid")
        core_generated = outcome_eligibility.parse_aware_time(core.get("generated_at"))
        if core_generated is not None and evaluation is not None and core_generated > evaluation:
            errors.add("core_authority_generated_after_evaluation")
        if _authority_attribution_mismatch(candidate, core):
            errors.add("candidate_core_attribution_mismatch")
    if (
        errors
        or evaluation is None
        or candidate_observed is None
        or core is None
        or primary_horizon is None
    ):
        return _result(None, errors, supplied_closes, ())

    observations, observation_errors = _observed_closes_for_asset(
        supplied_closes,
        symbol=str(symbol),
        coin_id=str(coin_id),
    )
    errors.update(observation_errors)
    if price_data_kind == "observed_market_prices" and any(
        _synthetic_lineage(observation) for observation in observations
    ):
        errors.add("synthetic_lineage_claimed_observed")
    if not observations:
        errors.add("price_observations_missing")
    if errors:
        return _result(None, errors, supplied_closes, observations)

    entry_candidates = [
        observation
        for observation in observations
        if observation.close_observed_at <= candidate_observed
    ]
    if not entry_candidates:
        errors.add("entry_price_missing")
        return _result(None, errors, supplied_closes, observations)
    entry = entry_candidates[-1]
    if (
        candidate_observed - entry.close_observed_at
    ).total_seconds() > outcome_eligibility.OUTCOME_ENTRY_PRICE_MAX_STALENESS_SECONDS:
        errors.add("entry_price_stale")
        return _result(None, errors, supplied_closes, observations)

    row = _outcome_row(
        candidate,
        core,
        observations,
        entry=entry,
        evaluated_at=evaluation,
        observed_at=candidate_observed,
        primary_horizon=primary_horizon,
        price_data_kind=price_data_kind,
    )
    eligible, excluded, _reason_counts = (
        outcome_eligibility.partition_joined_calibration_outcomes(
            [row],
            [candidate],
            [core],
            evaluated_at=evaluation,
        )
    )
    joined = dict((eligible or excluded)[0])
    materialized = dict(row)
    materialized["calibration_eligible"] = bool(joined.get("calibration_eligible"))
    materialized["calibration_ineligible_reasons"] = list(
        joined.get("calibration_ineligible_reasons") or ()
    )
    for field in outcome_eligibility.OUTCOME_ATTRIBUTION_FIELDS:
        if materialized.get(field) == "unknown":
            materialized.pop(field, None)
    materialized["include_in_performance"] = bool(eligible)
    materialized["validation_status"] = (
        outcome_eligibility.deterministic_validation_status(materialized)
        if eligible
        else "inconclusive"
    )
    return _result(materialized, (), supplied_closes, observations)


def _outcome_row(
    candidate: Mapping[str, Any],
    core: Mapping[str, Any],
    observations: tuple[_ObservedClose, ...],
    *,
    entry: _ObservedClose,
    evaluated_at: datetime,
    observed_at: datetime,
    primary_horizon: str,
    price_data_kind: str,
) -> dict[str, Any]:
    returns: dict[str, float | None] = {}
    metadata: dict[str, dict[str, Any]] = {}
    used_observation_ids = {entry.observation_id}
    for horizon in outcome_eligibility.OUTCOME_HORIZONS:
        due = observed_at + timedelta(
            seconds=outcome_eligibility.OUTCOME_HORIZON_SECONDS[horizon]
        )
        if evaluated_at < due:
            selected = None
            maturity_status = "pending"
        else:
            lag_seconds = min(
                outcome_eligibility.OUTCOME_HORIZON_SECONDS[horizon],
                24 * 60 * 60,
            )
            ceiling = min(
                evaluated_at,
                due + timedelta(seconds=lag_seconds),
            )
            selected = next(
                (
                    observation
                    for observation in observations
                    if due <= observation.close_observed_at <= ceiling
                    and observation.observation_id not in used_observation_ids
                ),
                None,
            )
            maturity_status = "matured" if selected is not None else "missing_data"
        if selected is not None:
            used_observation_ids.add(selected.observation_id)
            horizon_return = selected.close / entry.close - 1.0
        else:
            horizon_return = None
        returns[horizon] = horizon_return
        metadata[horizon] = {
            "due_at": outcome_eligibility.iso_utc(due),
            "price_observed_at": (
                outcome_eligibility.iso_utc(selected.close_observed_at)
                if selected is not None
                else None
            ),
            "price_at_horizon": selected.close if selected is not None else None,
            "price_source": selected.source if selected is not None else None,
            "price_observation_id": (
                selected.observation_id if selected is not None else None
            ),
            "maturity_status": maturity_status,
            "provenance_status": (
                price_data_kind if selected is not None else "missing"
            ),
        }

    identity_fields = outcome_eligibility.build_outcome_identity_fields(candidate)
    primary_return = returns[primary_horizon]
    primary_state = metadata[primary_horizon]["maturity_status"]
    row: dict[str, Any] = {
        "schema_id": "outcome_row_v1",
        "schema_version": "event_alpha_schema_v1",
        "row_type": "event_integrated_radar_outcome",
        **identity_fields,
        "outcome_eligibility_contract_version": (
            outcome_eligibility.OUTCOME_ELIGIBILITY_CONTRACT_VERSION
        ),
        "outcome_data_source": price_data_kind,
        "outcome_evaluated_at": outcome_eligibility.iso_utc(evaluated_at),
        "calibration_eligible": False,
        "calibration_ineligible_reasons": [],
        "symbol": candidate.get("symbol") or core.get("symbol"),
        "coin_id": candidate.get("coin_id") or core.get("coin_id"),
        "opportunity_type": candidate.get("opportunity_type"),
        "price_at_observation": entry.close,
        "observation_price_source": entry.source,
        "observation_price_id": entry.observation_id,
        "observation_price_observed_at": outcome_eligibility.iso_utc(
            entry.close_observed_at
        ),
        "observation_price_provenance_status": price_data_kind,
        "primary_horizon": primary_horizon,
        "primary_horizon_return": primary_return,
        "return_by_horizon": returns,
        "horizons": dict(returns),
        "horizon_metadata": metadata,
        "outcome_horizons": list(outcome_eligibility.OUTCOME_HORIZONS),
        "outcome_status": primary_state,
        "maturation_state": primary_state,
        "outcome_label": "inconclusive",
        "validation_status": "inconclusive",
        "include_in_performance": False,
        "price_data_status": price_data_kind,
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
        "paper_trade_created": False,
        "trade_created": False,
        "no_trade_created": True,
        "no_paper_trade_created": True,
    }
    for field in outcome_eligibility.OUTCOME_ATTRIBUTION_FIELDS:
        if field in row:
            continue
        value = candidate.get(field)
        if value in (None, "", (), []):
            value = core.get(field)
        if value not in (None, "", (), []):
            row[field] = value
    reasons = outcome_eligibility.calibration_ineligibility_reasons(row)
    row["calibration_ineligible_reasons"] = list(reasons)
    row["calibration_eligible"] = not reasons
    return row


def _observed_closes_for_asset(
    rows: Iterable[Mapping[str, Any]],
    *,
    symbol: str,
    coin_id: str,
) -> tuple[tuple[_ObservedClose, ...], tuple[str, ...]]:
    observations: list[_ObservedClose] = []
    errors: set[str] = set()
    for row in rows:
        if row.get("symbol") != symbol or row.get("coin_id") != coin_id:
            continue
        observed_at = outcome_eligibility.parse_aware_time(row.get("close_observed_at"))
        close = outcome_eligibility.finite_number(row.get("close"))
        source = row.get("source")
        observation_id = row.get("observation_id")
        if (
            observed_at is None
            or close is None
            or close <= 0
            or not _canonical_text(source)
            or not _canonical_text(observation_id)
        ):
            errors.add("invalid_close_observation")
            continue
        observations.append(
            _ObservedClose(
                symbol=symbol,
                coin_id=coin_id,
                close_observed_at=observed_at,
                close=close,
                source=str(source),
                observation_id=str(observation_id),
            )
        )
    id_counts: dict[str, int] = {}
    time_counts: dict[datetime, int] = {}
    for observation in observations:
        id_counts[observation.observation_id] = id_counts.get(observation.observation_id, 0) + 1
        time_counts[observation.close_observed_at] = (
            time_counts.get(observation.close_observed_at, 0) + 1
        )
    if any(count > 1 for count in id_counts.values()):
        errors.add("duplicate_close_observation_id")
    if any(count > 1 for count in time_counts.values()):
        errors.add("ambiguous_close_timestamp")
    ordered = tuple(
        sorted(
            observations,
            key=lambda item: (
                item.close_observed_at,
                item.source,
                item.observation_id,
            ),
        )
    )
    return ordered, tuple(sorted(errors))


def _authority_attribution_mismatch(
    candidate: Mapping[str, Any],
    core: Mapping[str, Any],
) -> bool:
    for field in ("symbol", "coin_id", "opportunity_type"):
        candidate_value = candidate.get(field)
        core_value = core.get(field)
        if (
            candidate_value not in (None, "")
            and core_value not in (None, "")
            and candidate_value != core_value
        ):
            return True
    return False


def _synthetic_lineage(observation: _ObservedClose) -> bool:
    source = observation.source.casefold()
    observation_id = observation.observation_id.casefold()
    return source.startswith(("fixture", "synthetic", "test_")) or (
        observation_id.startswith(("fixture:", "synthetic:", "test:"))
    )


def _core_context(row: Mapping[str, Any]) -> tuple[str, str, str, str] | None:
    values = tuple(
        row.get(field)
        for field in ("core_opportunity_id", "run_id", "profile", "artifact_namespace")
    )
    return (
        values  # type: ignore[return-value]
        if all(_canonical_text(value) for value in values)
        else None
    )


def _canonical_text(value: Any) -> bool:
    if type(value) is not str or not value or value != value.strip():
        return False
    if unicodedata.normalize("NFC", value) != value:
        return False
    return not any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in value
    )


def _result(
    outcome: dict[str, Any] | None,
    errors: Iterable[str],
    supplied: Iterable[Mapping[str, Any]],
    accepted: Iterable[_ObservedClose],
) -> _ObservedOutcomeBuildResult:
    return _ObservedOutcomeBuildResult(
        outcome=outcome,
        build_errors=tuple(sorted(set(errors))),
        observations_supplied=sum(1 for _row in supplied),
        observations_accepted=sum(1 for _row in accepted),
    )


__all__ = (
    "OBSERVED_OUTCOME_BUILD_ERRORS",
    "build_observed_outcome",
)
