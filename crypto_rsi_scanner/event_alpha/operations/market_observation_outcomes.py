"""Campaign-level observed outcomes over immutable Decision Radar generations.

Origin namespaces remain unchanged.  The mutable campaign ledger lives beside
the rolling market-history cache and is rebuilt deterministically from exact
candidate/Core rows plus observed CoinGecko prices.  It never calls providers,
sends notifications, creates trades, or changes decision thresholds.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..outcomes import outcome_eligibility
from ..outcomes.integrated_radar_outcome_rows import _outcome_placeholder_row
from ..outcomes.observed_outcome_builder import build_observed_outcome
from ..radar.decision_model_surfaces import decision_model_values
from . import market_no_send_publication
from .market_no_send_history_cache import LIVE_HISTORY_CACHE_NAMESPACE
from .market_no_send_io import read_json_object, read_jsonl, write_jsonl
from .market_no_send_models import SAFETY_COUNTERS


CAMPAIGN_OUTCOMES_FILENAME = "event_decision_radar_campaign_outcomes.jsonl"
_MANIFEST = "event_market_no_send_generation.json"
_CANDIDATES = "event_integrated_radar_candidates.jsonl"
_CORE = "event_core_opportunities.jsonl"
_HISTORY = "event_market_history.jsonl"


def refresh_campaign_outcomes(
    artifact_base_dir: str | Path,
    *,
    evaluated_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Rebuild observed outcomes from local artifacts only."""

    base = Path(artifact_base_dir).expanduser().resolve()
    evaluated = _aware_time(evaluated_at) or datetime.now(timezone.utc)
    history_dir = base / LIVE_HISTORY_CACHE_NAMESPACE
    history = read_jsonl(history_dir / _HISTORY)
    closes = [_close_row(row) for row in history]
    closes = [row for row in closes if row]
    campaign_path = history_dir / CAMPAIGN_OUTCOMES_FILENAME
    prior_rows = read_jsonl(campaign_path)
    prior_by_identity = _prior_outcomes_by_identity(prior_rows)
    materialized: list[dict[str, Any]] = []
    build_error_counts: Counter[str] = Counter()
    monotonic_preserved_count = 0
    current_identities: set[tuple[str, str]] = set()

    generation_records, excluded_generations = _real_generation_dirs(base)
    valid_namespaces = {path.name for path, _validation in generation_records}
    for namespace_dir, validation in generation_records:
        candidates = read_jsonl(namespace_dir / _CANDIDATES)
        core_rows = (
            read_jsonl(namespace_dir / _CORE)
            if validation.core_artifact_bound else []
        )
        existing = {
            str(row.get("candidate_id") or ""): row
            for row in (
                read_jsonl(namespace_dir / "event_integrated_radar_outcomes.jsonl")
                if validation.integrated_outcome_artifact_bound else []
            )
        }
        for candidate in candidates:
            candidate_id = str(candidate.get("candidate_id") or "")
            identity = (namespace_dir.name, candidate_id)
            current_identities.add(identity)
            projection = _canonical_candidate_projection(candidate)
            matching_cores, core_join_error = _matching_core_rows(
                candidate,
                core_rows,
                projection=projection,
            )
            outcome_core_rows = matching_cores
            authority_source = (
                "candidate_core_join"
                if matching_cores
                else "invalid_candidate_projection"
            )
            if not matching_cores and projection:
                derived_core = _candidate_projection_core(
                    candidate,
                    projection=projection,
                )
                if derived_core is not None:
                    outcome_core_rows = [derived_core]
                    authority_source = "canonical_decision_candidate"
            result = build_observed_outcome(
                [candidate],
                outcome_core_rows,
                closes,
                evaluated_at=evaluated,
                price_data_kind="observed_market_prices",
            ) if projection else None
            if result is not None and result.outcome is not None:
                row = dict(result.outcome)
                if authority_source == "canonical_decision_candidate":
                    _eligible, excluded, _reasons = (
                        outcome_eligibility.partition_joined_calibration_outcomes(
                            [row],
                            [candidate],
                            [],
                            evaluated_at=evaluated,
                        )
                    )
                    row = dict(excluded[0])
                    row["include_in_performance"] = False
            else:
                row = dict(existing.get(candidate_id) or _outcome_placeholder_row(
                    candidate,
                    now=evaluated.isoformat(),
                ))
                build_errors = (
                    result.build_errors
                    if result is not None
                    else ("candidate_decision_projection_invalid",)
                )
                row["campaign_outcome_refresh_errors"] = list(build_errors)
                build_error_counts.update(build_errors)
            if projection:
                row["decision_projection"] = deepcopy(projection)
                for key, value in projection.items():
                    row[key] = deepcopy(value)
            if core_join_error:
                prior_errors = row.get("campaign_outcome_refresh_errors")
                errors = list(prior_errors) if isinstance(prior_errors, list) else []
                row["campaign_outcome_refresh_errors"] = list(dict.fromkeys((*errors, core_join_error)))
                build_error_counts[core_join_error] += 1
            row.update({
                "measurement_program": "decision_radar_live_observation_campaign_v2",
                "source_artifact_namespace": namespace_dir.name,
                "campaign_outcome_ledger": True,
                "campaign_outcome_authority": authority_source,
                "campaign_core_opportunity_present": bool(matching_cores),
                "campaign_calibration_scope": (
                    "candidate_core_joined"
                    if matching_cores
                    else "candidate_only_not_core_joined"
                ),
                "research_only": True,
                "no_send_rehearsal": True,
                "sent": False,
                "trade_created": False,
                "paper_trade_created": False,
                "normal_rsi_signal_written": False,
                "triggered_fade_created": False,
            })
            prior = prior_by_identity.get(identity)
            preserved_prior = _preserves_prior_outcome(prior, row)
            selected = _monotonic_outcome(prior, row)
            if preserved_prior and row != prior:
                monotonic_preserved_count += 1
            materialized.append(selected)

    for identity, prior in prior_by_identity.items():
        if (
            identity in current_identities
            or identity[0] not in valid_namespaces
            or _outcome_state_rank(prior) <= 0
        ):
            continue
        materialized.append(prior)
        monotonic_preserved_count += 1

    return _write_campaign_outcome_ledger(
        history_dir=history_dir,
        campaign_path=campaign_path,
        materialized=materialized,
        build_error_counts=build_error_counts,
        validated_generation_count=len(generation_records),
        excluded_generations=excluded_generations,
        monotonic_preserved_count=monotonic_preserved_count,
        evaluated=evaluated,
    )


def _write_campaign_outcome_ledger(
    *,
    history_dir: Path,
    campaign_path: Path,
    materialized: list[dict[str, Any]],
    build_error_counts: Counter[str],
    validated_generation_count: int,
    excluded_generations: list[dict[str, Any]],
    monotonic_preserved_count: int,
    evaluated: datetime,
) -> dict[str, Any]:
    materialized.sort(key=lambda row: (
        str(row.get("observed_at") or ""),
        str(row.get("source_artifact_namespace") or ""),
        str(row.get("candidate_id") or ""),
    ))
    history_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    write_jsonl(campaign_path, materialized)
    states = Counter(
        str(row.get("maturation_state") or row.get("outcome_status") or "unknown")
        for row in materialized
    )
    return {
        "path": str(campaign_path),
        "outcome_count": len(materialized),
        "maturation_counts": dict(sorted(states.items())),
        "build_error_counts": dict(sorted(build_error_counts.items())),
        "validated_generation_count": validated_generation_count,
        "excluded_generation_count": len(excluded_generations),
        "excluded_generations": list(excluded_generations),
        "generation_validation_error_counts": dict(sorted(Counter(
            reason
            for row in excluded_generations
            for reason in row.get("validation_errors", ())
        ).items())),
        "monotonic_preserved_count": monotonic_preserved_count,
        "evaluated_at": evaluated.isoformat(),
        "provider_calls": 0,
        "research_only": True,
    }


def load_campaign_outcomes(artifact_base_dir: str | Path) -> list[dict[str, Any]]:
    base = Path(artifact_base_dir).expanduser().resolve()
    return read_jsonl(
        base / LIVE_HISTORY_CACHE_NAMESPACE / CAMPAIGN_OUTCOMES_FILENAME
    )


def candidate_pending_campaign_outcome(
    candidate: Mapping[str, Any],
    *,
    namespace: str,
) -> dict[str, Any]:
    """Return the fail-closed pending campaign identity for one bound candidate."""

    candidate_id = str(candidate.get("candidate_id") or "")
    identity_fields: dict[str, Any] = {}
    if outcome_eligibility.canonical_join_identity(candidate) is not None:
        identity_fields = outcome_eligibility.build_outcome_identity_fields(candidate)
    return {
        **identity_fields,
        "outcome_identity_key": identity_fields.get("outcome_identity_key") or f"candidate:{candidate_id}",
        "candidate_id": candidate_id,
        "source_artifact_namespace": namespace,
        "maturation_state": "pending",
        "campaign_outcome_ledger": False,
        "campaign_outcome_source": "canonical_candidate_pending_base",
        "research_only": True,
        "no_send_rehearsal": True,
        "sent": False,
        "trade_created": False,
        "paper_trade_created": False,
        "normal_rsi_signal_written": False,
        "triggered_fade_created": False,
    }


def campaign_ledger_outcome_valid(
    row: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    namespace: str,
) -> bool:
    """Validate one mutable outcome strictly against its immutable candidate."""

    projection = _canonical_candidate_projection(candidate)
    candidate_identity = outcome_eligibility.canonical_join_identity(candidate)
    declared = row.get("calibration_ineligible_reasons")
    if (
        not projection
        or candidate_identity is None
        or not isinstance(declared, list)
        or not all(type(reason) is str for reason in declared)
        or declared != sorted(set(declared))
    ):
        return False
    scope = row.get("campaign_calibration_scope")
    authority = row.get("campaign_outcome_authority")
    expected_pair = {
        "candidate_core_joined": "candidate_core_join",
        "candidate_only_not_core_joined": "canonical_decision_candidate",
    }
    if any((
        row.get("measurement_program") != "decision_radar_live_observation_campaign_v2",
        row.get("source_artifact_namespace") != namespace,
        row.get("candidate_id") != candidate.get("candidate_id"),
        row.get("campaign_outcome_ledger") is not True,
        expected_pair.get(str(scope)) != authority,
        row.get("campaign_core_opportunity_present") is not (scope == "candidate_core_joined"),
        outcome_eligibility.canonical_join_identity(row) != candidate_identity,
        row.get("outcome_identity_key") != outcome_eligibility.build_outcome_identity_fields(candidate)["outcome_identity_key"],
        row.get("decision_projection") != projection,
        decision_model_values(row) != projection,
        not _campaign_safety_valid(row),
    )):
        return False
    computed = set(outcome_eligibility.calibration_ineligibility_reasons(row))
    declared_set = set(declared)
    join_only = declared_set - computed
    if not computed.issubset(declared_set) or not join_only.issubset({"unmatched_outcome_identity"}):
        return False
    expected_eligible = not declared_set
    if row.get("calibration_eligible") is not expected_eligible:
        return False
    if row.get("include_in_performance") is not expected_eligible:
        return False
    return scope != "candidate_only_not_core_joined" or expected_eligible is False


def _real_generation_dirs(
    base: Path,
) -> tuple[
    tuple[tuple[Path, market_no_send_publication.CampaignGenerationValidation], ...],
    tuple[dict[str, Any], ...],
]:
    out: list[tuple[Path, market_no_send_publication.CampaignGenerationValidation]] = []
    excluded: list[dict[str, Any]] = []
    try:
        children = sorted(base.iterdir(), key=lambda item: item.name)
    except OSError:
        children = []
    for path in children:
        if not path.is_dir() or path.name in {
            LIVE_HISTORY_CACHE_NAMESPACE,
            "radar_market_no_send_smoke",
        }:
            continue
        manifest_path = path / _MANIFEST
        if not manifest_path.is_file():
            continue
        try:
            manifest = read_json_object(manifest_path)
        except (OSError, ValueError, RuntimeError):
            continue
        if not (
            manifest.get("status") == "complete"
            and manifest.get("data_mode") == "live"
            and manifest.get("provider_request_succeeded") is True
        ):
            continue
        validation = market_no_send_publication.validate_countable_campaign_generation(
            manifest,
            namespace_dir=path,
            namespace=path.name,
            contract_version=2,
            default_profile="no_key_live",
            request_cache_filename="event_market_no_send_market_rows.json",
            request_ledger_filename="event_market_no_send_request_ledger.json",
            safety_counters=SAFETY_COUNTERS,
            candidates_filename=_CANDIDATES,
        )
        if validation.valid:
            out.append((path, validation))
        else:
            excluded.append({
                "artifact_namespace": path.name,
                "run_id": manifest.get("run_id"),
                "observed_at": manifest.get("observed_at"),
                "validation_errors": list(validation.validation_errors),
                "campaign_counting_source": validation.counting_source,
                "campaign_counting_reason": validation.counting_reason,
            })
    return tuple(out), tuple(excluded)


def _close_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol"),
        "coin_id": row.get("coin_id") or row.get("canonical_asset_id"),
        "close_observed_at": row.get("observed_at"),
        "close": row.get("price"),
        "source": row.get("source") or row.get("provider") or "coingecko",
        "observation_id": row.get("observation_id"),
    }


def _canonical_candidate_projection(
    candidate: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Return one validated, closed candidate projection without re-evaluation."""

    if not outcome_eligibility.valid_candidate_authority(candidate):
        return None
    projection = decision_model_values(candidate)
    if not projection or projection.get("research_only") is not True:
        return None
    return projection


def _matching_core_rows(
    candidate: Mapping[str, Any],
    core_rows: list[dict[str, Any]],
    *,
    projection: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    context = _core_context(candidate)
    if context is None:
        return [], "candidate_core_identity_invalid"
    identity_matches = [row for row in core_rows if _core_context(row) == context]
    if not identity_matches:
        return [], None
    if len(identity_matches) != 1:
        return [], "core_authority_count_invalid"
    core = identity_matches[0]
    if not projection or decision_model_values(core) != dict(projection):
        return [], "core_decision_projection_mismatch"
    if not outcome_eligibility.valid_core_authority(core):
        return [], "core_authority_contract_invalid"
    return [core], None


def _candidate_projection_core(
    candidate: Mapping[str, Any],
    *,
    projection: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Build an in-memory authority adapter for candidate-only maturation.

    This row is never persisted as a CoreOpportunity.  It lets the existing
    observed-price builder reuse its strict identity, time, and price lineage
    checks while the campaign ledger records the candidate projection as the
    actual authority.
    """

    generated_at = outcome_eligibility.parse_aware_time(candidate.get("observed_at"))
    if generated_at is None:
        return None
    core = {
        **dict(candidate),
        "row_type": "event_core_opportunity",
        "schema_id": "core_opportunity_v1",
        "schema_version": "event_core_opportunity_store_v1",
        "generated_at": generated_at.isoformat(),
        "decision_projection": deepcopy(dict(projection)),
    }
    return core if outcome_eligibility.valid_core_authority(core) else None


def _core_context(row: Mapping[str, Any]) -> tuple[str, str, str, str] | None:
    values = tuple(
        row.get(field)
        for field in ("core_opportunity_id", "run_id", "profile", "artifact_namespace")
    )
    return values if all(type(value) is str and value for value in values) else None  # type: ignore[return-value]


def _prior_outcomes_by_identity(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Any]]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        identity = _campaign_identity(row)
        if identity is None or not _campaign_safety_valid(row):
            continue
        selected[identity] = _monotonic_outcome(selected.get(identity), row)
    return selected


def _campaign_identity(row: Mapping[str, Any]) -> tuple[str, str] | None:
    namespace = row.get("source_artifact_namespace")
    candidate_id = row.get("candidate_id")
    if not all(type(value) is str and value for value in (namespace, candidate_id)):
        return None
    return str(namespace), str(candidate_id)


def _campaign_safety_valid(row: Mapping[str, Any]) -> bool:
    return (
        row.get("research_only") is True
        and row.get("no_send_rehearsal") is True
        and all(
            row.get(field) is False
            for field in (
                "sent",
                "trade_created",
                "paper_trade_created",
                "normal_rsi_signal_written",
                "triggered_fade_created",
            )
        )
    )


def _monotonic_outcome(
    prior: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> dict[str, Any]:
    current_row = dict(current)
    if not isinstance(prior, Mapping):
        return current_row
    prior_row = dict(prior)
    if _preserves_prior_outcome(prior_row, current_row):
        return _refresh_preserved_campaign_metadata(prior_row, current_row)
    return current_row


def _preserves_prior_outcome(
    prior: Mapping[str, Any] | None,
    current: Mapping[str, Any],
) -> bool:
    if not isinstance(prior, Mapping):
        return False
    prior_rank = _outcome_state_rank(prior)
    current_rank = _outcome_state_rank(current)
    if prior_rank > current_rank:
        return True
    if prior_rank == current_rank and prior_rank > 0:
        return prior_rank == 1 or not _safely_extends_mature_outcome(prior, current)
    return False


def _refresh_preserved_campaign_metadata(
    prior: Mapping[str, Any],
    current: Mapping[str, Any],
) -> dict[str, Any]:
    """Keep terminal prices while upgrading candidate-owned campaign metadata."""

    preserved = dict(prior)
    for key in (
        "measurement_program",
        "source_artifact_namespace",
        "campaign_outcome_ledger",
        "campaign_outcome_authority",
        "campaign_core_opportunity_present",
        "campaign_calibration_scope",
        "research_only",
        "no_send_rehearsal",
        "sent",
        "trade_created",
        "paper_trade_created",
        "normal_rsi_signal_written",
        "triggered_fade_created",
    ):
        if key in current:
            preserved[key] = deepcopy(current[key])
    projection = current.get("decision_projection")
    if isinstance(projection, Mapping) and projection:
        preserved["decision_projection"] = deepcopy(dict(projection))
        for key, value in projection.items():
            preserved[key] = deepcopy(value)
    if current.get("campaign_calibration_scope") == "candidate_only_not_core_joined":
        preserved["calibration_eligible"] = False
        reasons = current.get("calibration_ineligible_reasons")
        preserved["calibration_ineligible_reasons"] = (
            deepcopy(list(reasons))
            if isinstance(reasons, list) and reasons
            else ["unmatched_outcome_identity"]
        )
        preserved["include_in_performance"] = False
    return preserved


def _outcome_state_rank(row: Mapping[str, Any]) -> int:
    values = {
        str(row.get(field) or "").casefold()
        for field in (
            "maturation_state",
            "outcome_status",
            "outcome_label",
            "validation_status",
            "validation_label",
        )
    }
    if values & {
        "matured",
        "filled",
        "complete",
        "closed",
        "terminal",
        "validated",
        "invalidated/noise",
    }:
        return 2
    if values & {"missing_data", "missing_price_data"}:
        return 1
    return 0


def _safely_extends_mature_outcome(
    prior: Mapping[str, Any],
    current: Mapping[str, Any],
) -> bool:
    """Accept only strictly additive maturity with unchanged prior price IDs."""

    prior_count = outcome_eligibility.filled_horizon_count(prior)
    current_count = outcome_eligibility.filled_horizon_count(current)
    if current_count <= prior_count:
        return False
    if any(
        prior.get(field) != current.get(field)
        for field in (
            "observation_price_id",
            "observation_price_observed_at",
            "price_at_observation",
        )
    ):
        return False
    prior_metadata = prior.get("horizon_metadata")
    current_metadata = current.get("horizon_metadata")
    prior_returns = prior.get("return_by_horizon")
    current_returns = current.get("return_by_horizon")
    if not all(
        isinstance(value, Mapping)
        for value in (prior_metadata, current_metadata, prior_returns, current_returns)
    ):
        return False
    for horizon in outcome_eligibility.OUTCOME_HORIZONS:
        prior_value = outcome_eligibility.finite_number(prior_returns.get(horizon))
        if prior_value is None:
            continue
        if prior_value != outcome_eligibility.finite_number(current_returns.get(horizon)):
            return False
        prior_horizon = prior_metadata.get(horizon)
        current_horizon = current_metadata.get(horizon)
        if not isinstance(prior_horizon, Mapping) or not isinstance(current_horizon, Mapping):
            return False
        if any(
            prior_horizon.get(field) != current_horizon.get(field)
            for field in (
                "price_observed_at",
                "price_at_horizon",
                "price_source",
                "price_observation_id",
            )
        ):
            return False
    return True


def _aware_time(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo is not None else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


__all__ = (
    "CAMPAIGN_OUTCOMES_FILENAME",
    "campaign_ledger_outcome_valid",
    "candidate_pending_campaign_outcome",
    "load_campaign_outcomes",
    "refresh_campaign_outcomes",
)
