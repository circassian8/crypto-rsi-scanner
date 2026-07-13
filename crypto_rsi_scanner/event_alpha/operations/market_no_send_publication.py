"""Manifest construction and guarded publication validation."""

from __future__ import annotations

import hashlib
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
from .market_no_send_io import read_json_object, read_regular_bytes
from .market_no_send_models import MarketNoSendError


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
        "burn_in_eligible": False,
        "burn_in_counted": False,
        "burn_in_reason": "generation_not_complete",
        "contract_counted_status": "not_counted",
        "no_send_status": "enforced",
        "no_send": True,
        "research_only": True,
        "pointer_published": False,
        **dict(safety_counters),
    }


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
    expected = _publishable_expectations(
        contract_version=contract_version,
        namespace=namespace,
        default_profile=default_profile,
        safety_counters=safety_counters,
    )
    mismatches = [key for key, value in expected.items() if manifest.get(key) != value]
    if mismatches:
        raise MarketNoSendError(
            "market generation provenance is not publishable (" + ",".join(mismatches[:6]) + ")"
        )
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        raise MarketNoSendError("market generation provenance has no exact run id")
    _validate_observation_clock(manifest.get("observed_at"), checked_at=checked_at)
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
    provenance = manifest.get("market_provenance")
    if not isinstance(provenance, Mapping):
        raise MarketNoSendError("market generation has no closed provenance projection")
    if (
        provenance.get("provider_source_artifact_sha256") != source_digest
        or provenance.get("request_ledger_sha256") != ledger_digest
    ):
        raise MarketNoSendError("market generation closed provenance drifted")
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
    expected = _request_expectations(
        contract_version=contract_version,
        namespace=namespace,
        run_id=run_id,
        safety_counters=safety_counters,
    )
    if any(source.get(key) != value for key, value in expected.items()):
        raise MarketNoSendError("market request-cache provenance is not publishable")
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
        "run_id": run_id,
        "data_mode": "live",
        "data_acquisition_mode": "live_provider",
        "candidate_source_mode": "live_no_send",
        "provider": "coingecko",
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
    digest = hashlib.sha256(read_regular_bytes(path)).hexdigest()
    if manifest.get("request_ledger_sha256") != digest:
        raise MarketNoSendError("market request-ledger fingerprint drifted")
    return digest


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
        "burn_in_eligible": True,
        "burn_in_counted": True,
        "burn_in_reason": "counted_live_no_send_exact_lineage",
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
        "run_mode": "burn_in",
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
