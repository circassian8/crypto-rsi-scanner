"""Manifest construction and guarded publication validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from ... import config
from ..artifacts import operator_state
from ..dashboard.readiness import (
    CURRENT_NAMESPACE_POINTER,
    DashboardReadinessError,
    read_current_namespace_pointer,
)
from .market_no_send_io import read_json_object, read_jsonl, read_regular_bytes
from .market_no_send_models import MarketNoSendError
from .market_provenance import DECISION_RADAR_MEASUREMENT_PROGRAM


INTEGRATED_CANDIDATES_FILENAME = "event_integrated_radar_candidates.jsonl"
CORE_OPPORTUNITIES_FILENAME = "event_core_opportunities.jsonl"
INTEGRATED_OUTCOMES_FILENAME = "event_integrated_radar_outcomes.jsonl"
PROVIDER_HEALTH_FILENAME = "event_provider_health.json"
PROVIDER_HEALTH_KEY = "market_universe:market_no_send"


@dataclass(frozen=True)
class CampaignGenerationValidation:
    """Closed, credential-free countability result for one immutable generation."""

    valid: bool
    campaign_counted: bool
    counting_source: str
    counting_reason: str
    validation_errors: tuple[str, ...]
    candidate_count: int
    legacy_adapter: bool
    core_artifact_bound: bool
    core_artifact_row_count: int
    integrated_outcome_artifact_bound: bool
    integrated_outcome_artifact_row_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "campaign_counted": self.campaign_counted,
            "counting_source": self.counting_source,
            "counting_reason": self.counting_reason,
            "validation_errors": list(self.validation_errors),
            "candidate_count": self.candidate_count,
            "legacy_adapter": self.legacy_adapter,
            "core_artifact_bound": self.core_artifact_bound,
            "core_artifact_row_count": self.core_artifact_row_count,
            "integrated_outcome_artifact_bound": self.integrated_outcome_artifact_bound,
            "integrated_outcome_artifact_row_count": self.integrated_outcome_artifact_row_count,
        }


def supporting_jsonl_artifact_bindings(
    core_path: Path,
    integrated_outcomes_path: Path,
) -> dict[str, Any]:
    """Return immutable manifest bindings for campaign-supporting JSONL artifacts."""

    return {
        **_jsonl_manifest_binding(core_path, prefix="core"),
        **_jsonl_manifest_binding(integrated_outcomes_path, prefix="integrated_outcome"),
    }


def assert_namespace_not_current_authority(base: Path, namespace: str) -> None:
    """Never mutate the namespace behind the authoritative dashboard pointer."""

    reason = namespace_mutation_blocker(base, namespace)
    if reason:
        raise MarketNoSendError(reason)


def namespace_mutation_blocker(base: Path, namespace: str) -> str | None:
    """Return a no-write blocker when a namespace cannot be safely mutated."""

    pointer_path = base / CURRENT_NAMESPACE_POINTER
    try:
        pointer_path.lstat()
    except FileNotFoundError:
        pointer = None
    except OSError:
        return "dashboard pointer is unreadable"
    else:
        try:
            pointer = read_current_namespace_pointer(base)
        except DashboardReadinessError:
            return "dashboard pointer is invalid; refusing namespace mutation"
    if pointer is not None and pointer.get("artifact_namespace") == namespace:
        return "market generation namespace is current dashboard authority"
    namespace_dir = base / namespace
    try:
        namespace_dir.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return "market generation namespace is unreadable"
    return "market generation namespace already exists; choose a new generation namespace"


def readiness_next_command(
    *,
    authorization_env: str,
    authorized: bool,
    fixture_mode: bool,
    namespace_blocker: str | None,
) -> str:
    if namespace_blocker and (
        "current dashboard authority" in namespace_blocker
        or "already exists" in namespace_blocker
    ):
        return (
            "Choose RADAR_MARKET_NO_SEND_NAMESPACE=<new-generation>, then run "
            "make radar-market-no-send"
        )
    if namespace_blocker:
        return "Repair or remove the invalid dashboard pointer, then rerun readiness"
    if not authorized:
        return f"Authorize {authorization_env}=1 outside Codex, then run make radar-market-no-send"
    if fixture_mode:
        return "Unset FIXTURE_DIR, then run make radar-market-no-send-readiness"
    return "make radar-market-no-send"


def base_manifest(
    *,
    context: Any,
    observed: datetime,
    data_mode: str,
    provider: str,
    authorized: bool,
    fixture_mode: bool,
    top_n: int,
    fetch_limit: int,
    status: str,
    contract_version: int,
    safety_counters: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "contract_version": contract_version,
        "row_type": "event_market_no_send_generation",
        "status": status,
        "profile": context.profile,
        "artifact_namespace": context.artifact_namespace,
        "run_mode": context.run_mode,
        "data_mode": data_mode,
        "data_acquisition_mode": "live_provider" if data_mode == "live" else "mocked_fixture",
        "candidate_source_mode": "live_no_send" if data_mode == "live" else "mocked_fixture",
        "provider": provider,
        "observed_at": observed.isoformat(),
        "top_n": top_n,
        "fetch_limit": fetch_limit,
        "live_provider_authorized": authorized,
        "fixture_mode": fixture_mode,
        "provider_call_attempted": False,
        "provider_request_succeeded": False,
        "provenance_contract_valid": False,
        "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": False,
        "decision_radar_campaign_counted": False,
        "decision_radar_campaign_reason": "generation_not_complete",
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "not_counted_separate_decision_radar_campaign",
        "contract_counted_status": "not_counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "pointer_published": False,
        **dict(safety_counters),
    }


def validate_countable_campaign_generation(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    contract_version: int,
    default_profile: str,
    request_cache_filename: str,
    request_ledger_filename: str,
    safety_counters: Mapping[str, int],
    candidates_filename: str = INTEGRATED_CANDIDATES_FILENAME,
) -> CampaignGenerationValidation:
    """Validate one countable Decision campaign generation without freshness I/O.

    The current campaign contract and the historical market-provenance-v2
    adapter are deliberately separate.  The adapter never rewrites or upgrades
    historical rows; it only admits an old row when its exact request, source,
    provider, candidate-count, and closed-provenance lineage still reconciles.
    """

    campaign_declared = bool(
        manifest.get("measurement_program") == DECISION_RADAR_MEASUREMENT_PROGRAM
        or "decision_radar_campaign_counted" in manifest
        or "decision_radar_campaign_eligible" in manifest
    )
    legacy_adapter = not campaign_declared
    source = (
        "historical_market_provenance_v2_read_only_adapter"
        if legacy_adapter
        else "decision_radar_campaign_contract"
    )
    errors: list[str] = []
    candidate_count = 0
    core_bound = outcome_bound = False
    core_count = outcome_count = 0
    try:
        if legacy_adapter:
            _validate_legacy_countable_lineage(
                manifest,
                namespace_dir=namespace_dir,
                namespace=namespace,
                contract_version=contract_version,
                default_profile=default_profile,
                request_cache_filename=request_cache_filename,
                request_ledger_filename=request_ledger_filename,
                safety_counters=safety_counters,
            )
        else:
            expected = _publishable_expectations(
                contract_version=contract_version,
                namespace=namespace,
                default_profile=default_profile,
                safety_counters=safety_counters,
            )
            mismatches = [
                key for key, value in expected.items() if manifest.get(key) != value
            ]
            if mismatches:
                raise MarketNoSendError(
                    "campaign_manifest_mismatch:" + ",".join(mismatches[:6])
                )
            run_id = _required_run_id(manifest)
            _require_observation_identity(manifest, run_id=run_id)
            source_digest = _validate_source_cache(
                manifest,
                namespace_dir=namespace_dir,
                namespace=namespace,
                run_id=run_id,
                filename=request_cache_filename,
                contract_version=contract_version,
                safety_counters=safety_counters,
            )
            ledger_digest = _validate_request_ledger(
                manifest,
                namespace_dir=namespace_dir,
                namespace=namespace,
                run_id=run_id,
                filename=request_ledger_filename,
                source_filename=request_cache_filename,
                source_digest=source_digest,
                contract_version=contract_version,
                safety_counters=safety_counters,
            )
            _validate_closed_provenance(
                manifest,
                source_digest=source_digest,
                ledger_digest=ledger_digest,
                run_id=run_id,
                legacy_adapter=False,
            )
        candidate_count = _validate_candidate_count(
            manifest,
            namespace_dir=namespace_dir,
            namespace=namespace,
            default_profile=default_profile,
            filename=candidates_filename,
            safety_counters=safety_counters,
            legacy_adapter=legacy_adapter,
        )
        core_bound, core_count = _validate_supporting_jsonl_artifact(
            manifest,
            namespace_dir=namespace_dir,
            filename=CORE_OPPORTUNITIES_FILENAME,
            prefix="core",
            operator_artifact_name="core_opportunities",
            legacy_adapter=legacy_adapter,
        )
        outcome_bound, outcome_count = _validate_supporting_jsonl_artifact(
            manifest,
            namespace_dir=namespace_dir,
            filename=INTEGRATED_OUTCOMES_FILENAME,
            prefix="integrated_outcome",
            operator_artifact_name="integrated_outcomes",
            legacy_adapter=legacy_adapter,
        )
    except (MarketNoSendError, OSError, TypeError, ValueError) as exc:
        errors.append(_validation_error_code(exc))
    valid = not errors
    reason = (
        "counted_valid_live_no_send_v2_lineage"
        if valid and legacy_adapter
        else "counted_live_no_send_exact_lineage"
        if valid
        else "excluded_invalid_generation:" + ",".join(errors)
    )
    return CampaignGenerationValidation(
        valid=valid,
        campaign_counted=valid,
        counting_source=source,
        counting_reason=reason,
        validation_errors=tuple(errors),
        candidate_count=candidate_count,
        legacy_adapter=legacy_adapter,
        core_artifact_bound=core_bound,
        core_artifact_row_count=core_count,
        integrated_outcome_artifact_bound=outcome_bound,
        integrated_outcome_artifact_row_count=outcome_count,
    )


def validate_publishable_manifest(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    checked_at: datetime,
    contract_version: int,
    default_profile: str,
    request_cache_filename: str,
    request_ledger_filename: str,
    safety_counters: Mapping[str, int],
) -> None:
    validation = validate_countable_campaign_generation(
        manifest,
        namespace_dir=namespace_dir,
        namespace=namespace,
        contract_version=contract_version,
        default_profile=default_profile,
        request_cache_filename=request_cache_filename,
        request_ledger_filename=request_ledger_filename,
        safety_counters=safety_counters,
    )
    if not validation.valid or validation.legacy_adapter:
        raise MarketNoSendError(
            "market generation provenance is not publishable ("
            + ",".join(validation.validation_errors or ("legacy_adapter",))
            + ")"
        )
    _validate_observation_clock(manifest.get("observed_at"), checked_at=checked_at)
    _validate_operator_market_provenance(
        namespace_dir,
        manifest=manifest,
        default_profile=default_profile,
    )


def _publishable_expectations(
    *,
    contract_version: int,
    namespace: str,
    default_profile: str,
    safety_counters: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "contract_version": contract_version,
        "status": "complete",
        "profile": default_profile,
        "artifact_namespace": namespace,
        "run_mode": "operational",
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provenance_contract_valid": True,
        "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": True,
        "decision_radar_campaign_counted": True,
        "decision_radar_campaign_reason": "counted_live_no_send_exact_lineage",
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "not_counted_separate_decision_radar_campaign",
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "pointer_published": False,
        **dict(safety_counters),
    }


def _validate_observation_clock(value: Any, *, checked_at: datetime) -> None:
    observed = _parse_time(value)
    if observed is None:
        raise MarketNoSendError("market generation provenance has an invalid observation clock")
    observed = observed.astimezone(timezone.utc)
    if observed > checked_at + timedelta(minutes=5):
        raise MarketNoSendError("market generation provenance is future-dated")
    max_age = max(0.25, float(config.EVENT_ALPHA_MAX_RUN_AGE_HOURS))
    if checked_at - observed > timedelta(hours=max_age):
        raise MarketNoSendError("market generation provenance is stale")


def _validate_source_cache(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    run_id: str,
    filename: str,
    contract_version: int,
    safety_counters: Mapping[str, int],
) -> str:
    if manifest.get("request_cache_artifact") != filename:
        raise MarketNoSendError("market generation request-cache lineage is invalid")
    path = namespace_dir / filename
    source = read_json_object(path)
    if source.get("row_type") != "event_market_no_send_source_cache":
        raise MarketNoSendError("campaign_source_cache_row_type_invalid")
    expected = _request_expectations(
        contract_version=contract_version,
        namespace=namespace,
        run_id=run_id,
        safety_counters=safety_counters,
    )
    if any(source.get(key) != value for key, value in expected.items()):
        raise MarketNoSendError("market request-cache provenance is not publishable")
    _validate_request_counts(source, manifest=manifest, expect_rows=True)
    digest = hashlib.sha256(read_regular_bytes(path)).hexdigest()
    if manifest.get("request_cache_sha256") != digest:
        raise MarketNoSendError("market request-cache fingerprint drifted")
    return digest


def _request_expectations(
    *,
    contract_version: int,
    namespace: str,
    run_id: str,
    safety_counters: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "contract_version": contract_version,
        "artifact_namespace": namespace,
        "run_mode": "operational",
        "run_id": run_id,
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provenance_contract_valid": True,
        "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": True,
        "decision_radar_campaign_counted": True,
        "decision_radar_campaign_reason": "counted_live_no_send_exact_lineage",
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "not_counted_separate_decision_radar_campaign",
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **dict(safety_counters),
    }


def _validate_request_ledger(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    run_id: str,
    filename: str,
    source_filename: str,
    source_digest: str,
    contract_version: int,
    safety_counters: Mapping[str, int],
) -> str:
    if manifest.get("request_ledger_artifact") != filename:
        raise MarketNoSendError("market generation request-ledger lineage is invalid")
    path = namespace_dir / filename
    ledger = read_json_object(path)
    if ledger.get("row_type") != "event_market_no_send_request_ledger":
        raise MarketNoSendError("campaign_request_ledger_row_type_invalid")
    expected = _ledger_expectations(
        contract_version=contract_version,
        namespace=namespace,
        run_id=run_id,
        source_filename=source_filename,
        source_digest=source_digest,
        safety_counters=safety_counters,
    )
    if any(ledger.get(key) != value for key, value in expected.items()):
        raise MarketNoSendError("market request-ledger provenance is not publishable")
    _validate_request_counts(ledger, manifest=manifest, expect_rows=False)
    _validate_campaign_request_telemetry(
        ledger,
        namespace_dir=namespace_dir,
        manifest=manifest,
    )
    digest = hashlib.sha256(read_regular_bytes(path)).hexdigest()
    if manifest.get("request_ledger_sha256") != digest:
        raise MarketNoSendError("market request-ledger fingerprint drifted")
    return digest


def _validate_campaign_request_telemetry(
    ledger: Mapping[str, Any],
    *,
    namespace_dir: Path,
    manifest: Mapping[str, Any],
) -> None:
    """Validate v2 campaign telemetry while retaining historical v2 reads."""

    if ledger.get("measurement_program") != "decision_radar_live_observation_campaign_v2":
        return
    if ledger.get("endpoint_path") != "/coins/markets":
        raise MarketNoSendError("market request-ledger endpoint is invalid")
    started = _parse_time(ledger.get("request_started_at"))
    ended = _parse_time(ledger.get("request_ended_at"))
    if started is None or ended is None or ended < started:
        raise MarketNoSendError("market request-ledger timing is invalid")
    for field in ("duration_ms", "result_count", "retry_count"):
        value = ledger.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise MarketNoSendError(f"market request-ledger {field} is invalid")
    if (
        ledger.get("http_status") != 200
        or ledger.get("error_class") is not None
        or ledger.get("cache_behavior") != "network"
        or ledger.get("result_count") != manifest.get("raw_market_row_count")
    ):
        raise MarketNoSendError("market request-ledger HTTP result is inconsistent")
    forbidden = {
        "headers", "query", "params", "token", "api_key", "authorization",
        "recipient", "recipient_id", "chat_id",
    }
    if forbidden.intersection(str(key).casefold() for key in ledger):
        raise MarketNoSendError("market request-ledger contains forbidden request material")
    health_path = namespace_dir / "event_provider_health.json"
    health = read_json_object(health_path)
    providers = health.get("providers")
    row = providers.get("market_universe:market_no_send") if isinstance(providers, Mapping) else None
    if not isinstance(row, Mapping) or any((
        row.get("run_id") != ledger.get("run_id"),
        row.get("request_http_status") != ledger.get("http_status"),
        row.get("request_result_count") != ledger.get("result_count"),
        row.get("request_retry_count") != ledger.get("retry_count"),
        row.get("last_error_class") is not None,
    )):
        raise MarketNoSendError("market provider health does not reconcile with request ledger")


def _ledger_expectations(
    *,
    contract_version: int,
    namespace: str,
    run_id: str,
    source_filename: str,
    source_digest: str,
    safety_counters: Mapping[str, int],
) -> dict[str, Any]:
    return {
        "contract_version": contract_version,
        "artifact_namespace": namespace,
        "run_mode": "operational",
        "run_id": run_id,
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provider_source_artifact": source_filename,
        "provider_source_artifact_sha256": source_digest,
        "provenance_contract_valid": True,
        "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
        "decision_radar_campaign_eligible": True,
        "decision_radar_campaign_counted": True,
        "decision_radar_campaign_reason": "counted_live_no_send_exact_lineage",
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "not_counted_separate_decision_radar_campaign",
        "contract_counted_status": "counted",
        "cache_status": "write_through",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **dict(safety_counters),
    }


def _validate_operator_market_provenance(
    namespace_dir: Path,
    *,
    manifest: Mapping[str, Any],
    default_profile: str,
) -> None:
    loaded = operator_state.load_operator_state(namespace_dir)
    state = dict(loaded.state or {}) if loaded.valid else {}
    expected_identity = {
        "run_id": manifest.get("run_id"),
        "profile": default_profile,
        "artifact_namespace": manifest.get("artifact_namespace"),
        "run_mode": "operational",
    }
    if any(state.get(field) != value for field, value in expected_identity.items()):
        raise MarketNoSendError("operator state identity does not match the live generation")
    provenance = state.get("market_no_send_provenance")
    expected = manifest.get("market_provenance")
    if (
        not isinstance(expected, Mapping)
        or not isinstance(provenance, Mapping)
        or dict(provenance) != dict(expected)
    ):
        raise MarketNoSendError("operator market provenance does not match the live generation")


def _required_run_id(manifest: Mapping[str, Any]) -> str:
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip() or run_id != run_id.strip():
        raise MarketNoSendError("campaign_run_id_invalid")
    return run_id


def _require_observation_identity(
    manifest: Mapping[str, Any],
    *,
    run_id: str,
) -> None:
    observed = _parse_time(manifest.get("observed_at"))
    if observed is None:
        raise MarketNoSendError("campaign_observed_at_invalid")
    profile = manifest.get("profile")
    if not isinstance(profile, str) or not profile:
        raise MarketNoSendError("campaign_profile_invalid")
    expected_run_id = f"{observed.isoformat()}|{profile}"
    if run_id != expected_run_id:
        raise MarketNoSendError("campaign_run_id_observation_mismatch")


def _validate_closed_provenance(
    manifest: Mapping[str, Any],
    *,
    source_digest: str,
    ledger_digest: str,
    run_id: str,
    legacy_adapter: bool,
) -> None:
    provenance = manifest.get("market_provenance")
    if not isinstance(provenance, Mapping):
        raise MarketNoSendError("campaign_closed_provenance_missing")
    expected = {
        "schema_version": "crypto_radar_market_provenance_v2",
        "contract_version": 2,
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "provider_call_attempted": True,
        "provider_call_succeeded": True,
        "live_provider_authorized": True,
        "request_ledger_path": "event_market_no_send_request_ledger.json",
        "request_ledger_sha256": ledger_digest,
        "provider_source_artifact": "event_market_no_send_market_rows.json",
        "provider_source_artifact_sha256": source_digest,
        "provider_generation_id": run_id,
        "cache_status": "write_through",
        "provenance_contract_valid": True,
        "burn_in_eligible": True if legacy_adapter else False,
        "burn_in_counted": True if legacy_adapter else False,
        "burn_in_reason": (
            "counted_live_no_send_exact_lineage"
            if legacy_adapter
            else "not_counted_separate_decision_radar_campaign"
        ),
    }
    if not legacy_adapter:
        expected.update({
            "measurement_program": DECISION_RADAR_MEASUREMENT_PROGRAM,
            "decision_radar_campaign_eligible": True,
            "decision_radar_campaign_counted": True,
            "decision_radar_campaign_reason": "counted_live_no_send_exact_lineage",
        })
    mismatches = [
        field for field, value in expected.items() if provenance.get(field) != value
    ]
    if mismatches:
        raise MarketNoSendError(
            "campaign_closed_provenance_mismatch:" + ",".join(mismatches[:6])
        )
    validation_errors = provenance.get("validation_errors")
    if validation_errors != []:
        raise MarketNoSendError("campaign_closed_provenance_validation_errors")
    for field in ("feature_basis", "data_quality"):
        if not isinstance(provenance.get(field), Mapping) or not provenance.get(field):
            raise MarketNoSendError(f"campaign_closed_provenance_{field}_invalid")


def _validate_candidate_count(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    default_profile: str,
    filename: str,
    safety_counters: Mapping[str, int],
    legacy_adapter: bool,
) -> int:
    raw = read_regular_bytes(namespace_dir / filename)
    if raw is None:
        raise MarketNoSendError("campaign_candidates_missing")
    try:
        candidates = read_jsonl(namespace_dir / filename)
    except (UnicodeDecodeError, ValueError) as exc:
        raise MarketNoSendError("campaign_candidates_invalid") from exc
    declared = manifest.get("candidate_count")
    if isinstance(declared, bool) or not isinstance(declared, int) or declared < 0:
        raise MarketNoSendError("campaign_candidate_count_invalid")
    if declared != len(candidates):
        raise MarketNoSendError("campaign_candidate_count_mismatch")
    digest = hashlib.sha256(raw).hexdigest()
    if legacy_adapter and manifest.get("candidate_artifact_sha256") in (None, ""):
        _validate_operator_candidate_binding(
            manifest, namespace_dir=namespace_dir, namespace=namespace,
            filename=filename, raw=raw, candidate_count=len(candidates),
        )
    elif (
        manifest.get("candidate_artifact") != filename
        or manifest.get("candidate_artifact_sha256") != digest
    ):
        raise MarketNoSendError("campaign_candidate_artifact_digest_mismatch")
    if any(manifest.get(field) != value for field, value in safety_counters.items()):
        raise MarketNoSendError("campaign_candidate_safety_counter_mismatch")
    run_id = manifest.get("run_id")
    provenance = manifest.get("market_provenance")
    for row in candidates:
        if any((
            row.get("artifact_namespace") != namespace,
            row.get("run_id") != run_id,
            row.get("profile") != default_profile,
            row.get("research_only") is not True,
            row.get("notification_send_enabled") is not False,
            row.get("paper_trade_created") is not False,
            row.get("normal_rsi_signal_written") is not False,
            row.get("triggered_fade_created") is not False,
            not isinstance(provenance, Mapping),
            row.get("market_provenance") != provenance,
        )):
            raise MarketNoSendError("campaign_candidate_lineage_mismatch")
    return len(candidates)


def _jsonl_manifest_binding(path: Path, *, prefix: str) -> dict[str, Any]:
    raw = read_regular_bytes(path)
    if raw is None:
        raise MarketNoSendError(f"campaign_{prefix}_artifact_missing")
    try:
        rows = read_jsonl(path)
    except (UnicodeDecodeError, ValueError) as exc:
        raise MarketNoSendError(f"campaign_{prefix}_artifact_invalid") from exc
    return {
        f"{prefix}_artifact": path.name,
        f"{prefix}_artifact_sha256": hashlib.sha256(raw).hexdigest(),
        f"{prefix}_artifact_row_count": len(rows),
    }


def _validate_supporting_jsonl_artifact(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    filename: str,
    prefix: str,
    operator_artifact_name: str,
    legacy_adapter: bool,
) -> tuple[bool, int]:
    """Validate required v2 bindings or a present historical operator binding."""

    path = namespace_dir / filename
    if not legacy_adapter:
        expected = _jsonl_manifest_binding(path, prefix=prefix)
        if any(manifest.get(field) != value for field, value in expected.items()):
            raise MarketNoSendError(f"campaign_{prefix}_artifact_binding_mismatch")
        return True, int(expected[f"{prefix}_artifact_row_count"])
    state = read_json_object(namespace_dir / "event_alpha_operator_state.json")
    artifacts = state.get("artifacts")
    binding = artifacts.get(operator_artifact_name) if isinstance(artifacts, Mapping) else None
    if not isinstance(binding, Mapping) or binding.get("status") != "current":
        return False, 0
    expected = _jsonl_manifest_binding(path, prefix=prefix)
    count = int(expected[f"{prefix}_artifact_row_count"])
    if any((
        binding.get("path") != filename,
        binding.get("run_id") != manifest.get("run_id"),
        binding.get("sha256") != expected[f"{prefix}_artifact_sha256"],
        binding.get("size_bytes") != len(read_regular_bytes(path) or b""),
        binding.get("item_count") != count,
    )):
        raise MarketNoSendError(f"legacy_campaign_{prefix}_binding_mismatch")
    return True, count


def _validate_operator_candidate_binding(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    filename: str,
    raw: bytes,
    candidate_count: int,
) -> None:
    state = read_json_object(namespace_dir / "event_alpha_operator_state.json")
    if any((
        state.get("artifact_namespace") != namespace,
        state.get("run_id") != manifest.get("run_id"),
        state.get("profile") != manifest.get("profile"),
        state.get("run_mode") != manifest.get("run_mode"),
        state.get("market_no_send_provenance") != manifest.get("market_provenance"),
    )):
        raise MarketNoSendError("legacy_campaign_operator_identity_mismatch")
    artifacts = state.get("artifacts")
    binding = artifacts.get("integrated_candidates") if isinstance(artifacts, Mapping) else None
    expected = {
        "status": "current", "path": filename,
        "run_id": manifest.get("run_id"), "count": candidate_count,
        "item_count": candidate_count, "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if not isinstance(binding, Mapping) or any(
        binding.get(field) != value for field, value in expected.items()
    ):
        raise MarketNoSendError("legacy_campaign_candidate_binding_mismatch")


def _validate_legacy_countable_lineage(
    manifest: Mapping[str, Any],
    *,
    namespace_dir: Path,
    namespace: str,
    contract_version: int,
    default_profile: str,
    request_cache_filename: str,
    request_ledger_filename: str,
    safety_counters: Mapping[str, int],
) -> None:
    expected = {
        "contract_version": contract_version,
        "status": "complete",
        "profile": default_profile,
        "artifact_namespace": namespace,
        "run_mode": "burn_in",
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "provenance_contract_valid": True,
        "burn_in_eligible": True,
        "burn_in_counted": True,
        "burn_in_reason": "counted_live_no_send_exact_lineage",
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "pointer_published": False,
        **dict(safety_counters),
    }
    mismatches = [field for field, value in expected.items() if manifest.get(field) != value]
    if mismatches:
        raise MarketNoSendError(
            "legacy_campaign_manifest_mismatch:" + ",".join(mismatches[:6])
        )
    run_id = _required_run_id(manifest)
    _require_observation_identity(manifest, run_id=run_id)
    source_name = manifest.get("request_cache_artifact")
    ledger_name = manifest.get("request_ledger_artifact")
    if source_name != request_cache_filename or ledger_name != request_ledger_filename:
        raise MarketNoSendError("legacy_campaign_artifact_names_invalid")
    source_path = namespace_dir / request_cache_filename
    ledger_path = namespace_dir / request_ledger_filename
    source = read_json_object(source_path)
    ledger = read_json_object(ledger_path)
    common = {
        "contract_version": contract_version,
        "profile": default_profile,
        "artifact_namespace": namespace,
        "run_mode": "burn_in",
        "run_id": run_id,
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
        "observed_at": manifest.get("observed_at"),
        "provider_call_attempted": True,
        "provider_request_succeeded": True,
        "raw_market_row_count": manifest.get("raw_market_row_count"),
        "selected_market_row_count": manifest.get("selected_market_row_count"),
        "provenance_contract_valid": True,
        "burn_in_eligible": True,
        "burn_in_counted": True,
        "burn_in_reason": "counted_live_no_send_exact_lineage",
        "contract_counted_status": "counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        **dict(safety_counters),
    }
    if source.get("row_type") != "event_market_no_send_source_cache" or any(
        source.get(field) != value for field, value in common.items()
    ):
        raise MarketNoSendError("legacy_campaign_source_lineage_invalid")
    rows = source.get("rows")
    if not isinstance(rows, list) or len(rows) != manifest.get("selected_market_row_count"):
        raise MarketNoSendError("legacy_campaign_source_count_mismatch")
    source_digest = hashlib.sha256(read_regular_bytes(source_path) or b"").hexdigest()
    if manifest.get("request_cache_sha256") != source_digest:
        raise MarketNoSendError("legacy_campaign_source_digest_mismatch")
    ledger_expected = {
        **common,
        "row_type": "event_market_no_send_request_ledger",
        "live_provider_authorized": True,
        "fixture_mode": False,
        "provider_source_artifact": request_cache_filename,
        "provider_source_artifact_sha256": source_digest,
        "cache_status": "write_through",
    }
    if any(ledger.get(field) != value for field, value in ledger_expected.items()):
        raise MarketNoSendError("legacy_campaign_request_lineage_invalid")
    ledger_digest = hashlib.sha256(read_regular_bytes(ledger_path) or b"").hexdigest()
    if manifest.get("request_ledger_sha256") != ledger_digest:
        raise MarketNoSendError("legacy_campaign_request_digest_mismatch")
    _validate_legacy_provider_health(
        namespace_dir,
        ledger=ledger,
        run_id=run_id,
    )
    _validate_closed_provenance(
        manifest,
        source_digest=source_digest,
        ledger_digest=ledger_digest,
        run_id=run_id,
        legacy_adapter=True,
    )


def _validate_legacy_provider_health(
    namespace_dir: Path,
    *,
    ledger: Mapping[str, Any],
    run_id: str,
) -> None:
    health = read_json_object(namespace_dir / PROVIDER_HEALTH_FILENAME)
    if health.get("schema_version") != "event_provider_health_v1":
        raise MarketNoSendError("legacy_campaign_provider_health_invalid")
    providers = health.get("providers")
    row = providers.get(PROVIDER_HEALTH_KEY) if isinstance(providers, Mapping) else None
    if not isinstance(row, Mapping) or any((
        row.get("provider") != "coingecko",
        row.get("run_id") != run_id,
        row.get("last_error_class") is not None,
        row.get("no_send") is not True,
        row.get("research_only") is not True,
    )):
        raise MarketNoSendError("legacy_campaign_provider_health_invalid")
    telemetry_fields = {
        "request_http_status": "http_status",
        "request_result_count": "result_count",
        "request_retry_count": "retry_count",
    }
    for health_field, ledger_field in telemetry_fields.items():
        if health_field in row and row.get(health_field) != ledger.get(ledger_field):
            raise MarketNoSendError("legacy_campaign_provider_health_drift")


def _validate_request_counts(
    row: Mapping[str, Any],
    *,
    manifest: Mapping[str, Any],
    expect_rows: bool,
) -> None:
    for field in ("raw_market_row_count", "selected_market_row_count"):
        value = manifest.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise MarketNoSendError(f"campaign_manifest_{field}_invalid")
        if row.get(field) != value:
            raise MarketNoSendError(f"campaign_{field}_mismatch")
    if row.get("observed_at") != manifest.get("observed_at"):
        raise MarketNoSendError("campaign_request_observed_at_mismatch")
    if expect_rows:
        rows = row.get("rows")
        if not isinstance(rows, list) or len(rows) != manifest.get(
            "selected_market_row_count"
        ):
            raise MarketNoSendError("campaign_source_count_mismatch")


def _validation_error_code(error: BaseException) -> str:
    text = str(error).strip()
    if not text:
        return type(error).__name__
    safe = "".join(
        character if character.isalnum() or character in "_:-,." else "_"
        for character in text[:240]
    ).strip("_")
    return safe or type(error).__name__


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else None
    return None
