"""Separately attested hardening supplement for the immutable v1 report bundle.

The seven Protocol-v1 reports and their bundle identifier are immutable inputs,
never outputs of this module.  The supplement binds their exact bytes to one
verified development/validation selection run, then adds descriptive
route-conditioned calibration and outcome-blind market-risk diagnostics.  It
does not read or select from the Protocol-v1 final-test run.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from ..artifacts.json_lines import loads_no_duplicate_keys
from . import (
    empirical_hardening_io,
    empirical_report_diagnostic_validation,
    empirical_report_diagnostics,
    empirical_replay_analysis,
    empirical_replay_persistence,
    empirical_replay_store,
    empirical_research_reports,
    empirical_validation_protocol,
)


SCHEMA_ID = "decision_radar.empirical_hardening_supplement"
SCHEMA_VERSION = 1
SUPPLEMENT_FILENAME = "DECISION_RADAR_EMPIRICAL_HARDENING_SUPPLEMENT.json"
MAX_SUPPLEMENT_BYTES = 4 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_SOURCE_COMPONENT_BYTES = 4 * 1024 * 1024
MAX_SELECTION_ARTIFACTS = 128
SELECTION_PARTITIONS = ("development", "validation")

DIAGNOSTICS_ALGORITHM_CONTRACT_SCHEMA_ID = (
    "decision_radar.empirical_diagnostics_algorithm_contract"
)
DIAGNOSTICS_ALGORITHM_CONTRACT_SCHEMA_VERSION = 1

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "status",
        "v1_report_bundle",
        "selection_run",
        "partitions",
        "partition_policy",
        "holdout_accessed",
        "final_test_data_accessed",
        "raw_final_test_run_accessed",
        "sealed_v1_report_summaries_used_for_operator_display_only",
        "operator_summary",
        "route_conditioned_calibration",
        "market_wide_risk_diagnostics",
        "diagnostics_algorithm_contract",
        "research_only",
        "auto_apply",
        "policy_eligible",
        "safety",
        "supplement_id",
    }
)
_REPORT_BINDING_KEYS = frozenset(
    {
        "bundle_id",
        "protocol_version",
        "protocol_sha256",
        "report_artifacts",
        "report_sha256",
        "report_count",
        "immutable",
    }
)
_SELECTION_BINDING_KEYS = frozenset(
    {
        "run_fingerprint",
        "protocol_version",
        "protocol_sha256",
        "input_sha256",
        "code_sha256",
        "configuration_sha256",
        "manifest_sha256",
        "artifact_sha256",
        "partitions",
        "holdout_accessed",
        "final_test_data_accessed",
        "immutable",
    }
)
_ALGORITHM_CONTRACT_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "diagnostic_schema_version",
        "route_calibration_schema_id",
        "market_risk_schema_id",
        "selection_partitions",
        "component_sha256",
        "contract_digest",
    }
)
_ALGORITHM_COMPONENTS = {
    "empirical_hardening_supplement.py": lambda: __file__,
    "empirical_hardening_io.py": lambda: empirical_hardening_io.__file__,
    "empirical_report_diagnostic_validation.py": lambda: (
        empirical_report_diagnostic_validation.__file__
    ),
    "empirical_report_diagnostics.py": lambda: empirical_report_diagnostics.__file__,
    "empirical_replay_analysis.py": lambda: empirical_replay_analysis.__file__,
    "empirical_replay_persistence.py": lambda: empirical_replay_persistence.__file__,
    "empirical_replay_store.py": lambda: empirical_replay_store.__file__,
    "empirical_validation_protocol.py": lambda: empirical_validation_protocol.__file__,
    "market_units.py": lambda: empirical_report_diagnostics.market_units.__file__,
}

_DirectoryAnchor = empirical_hardening_io.DirectoryAnchor
_absolute_path = empirical_hardening_io.absolute_path
_anchored_directory = empirical_hardening_io.anchored_directory
_assert_anchor_current = empirical_hardening_io.assert_anchor_current
_directory_names = empirical_hardening_io.directory_names
_entry_stat = empirical_hardening_io.entry_stat
_read_absolute_regular_file = empirical_hardening_io.read_absolute_regular_file
_read_regular_leaf = empirical_hardening_io.read_regular_leaf
_safe_leaf_name = empirical_hardening_io.safe_leaf_name

_DIGEST_FIELDS = (
    "protocol_sha256",
    "input_sha256",
    "code_sha256",
    "configuration_sha256",
    "manifest_sha256",
)
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


@dataclass(frozen=True)
class HardeningSupplementResult:
    path: Path
    supplement_id: str
    payload: bytes
    checked: bool
    resumed: bool


@dataclass(frozen=True)
class _PreparedSupplement:
    report_dir: Path
    report_payloads: dict[str, bytes]
    report_sha256: dict[str, str]
    value: dict[str, Any]
    payload: bytes


def build_hardening_supplement(
    *,
    selection_run: str | Path,
    report_dir: str | Path,
) -> dict[str, Any]:
    """Build a deterministic supplement without writing any artifact."""

    return dict(_prepare(selection_run=selection_run, report_dir=report_dir).value)


def canonical_supplement_bytes(value: Mapping[str, Any]) -> bytes:
    """Return the canonical wire representation used by the supplement ID."""

    return empirical_replay_store.canonical_json_bytes(dict(value))


def write_hardening_supplement(
    *,
    selection_run: str | Path,
    report_dir: str | Path,
    check: bool = False,
) -> HardeningSupplementResult:
    """Create, resume, or byte-check one immutable supplement."""

    with _anchored_directory(report_dir) as anchor:
        prepared = _prepare(
            selection_run=selection_run,
            report_dir=report_dir,
            report_anchor=anchor,
        )
        existing = _entry_stat(anchor.fd, SUPPLEMENT_FILENAME)
        resumed = False
        if existing is not None:
            if not stat.S_ISREG(existing.st_mode):
                raise RuntimeError("empirical_hardening_supplement_output_unsafe")
            observed = _read_regular_leaf(
                anchor.fd,
                SUPPLEMENT_FILENAME,
                maximum=MAX_SUPPLEMENT_BYTES,
            )
            if observed != prepared.payload:
                error = (
                    "empirical_hardening_supplement_check_failed"
                    if check
                    else "empirical_hardening_supplement_immutable_drift"
                )
                raise RuntimeError(error)
            resumed = not check
        elif check:
            raise RuntimeError("empirical_hardening_supplement_check_missing")
        else:
            _assert_reports_current(anchor, prepared)
            _publish_supplement_no_clobber(anchor, prepared)
        _validate_bound_output(anchor, prepared)
    return HardeningSupplementResult(
        path=prepared.report_dir / SUPPLEMENT_FILENAME,
        supplement_id=str(prepared.value["supplement_id"]),
        payload=prepared.payload,
        checked=check,
        resumed=resumed,
    )


def validate_hardening_supplement(
    value: Mapping[str, Any],
    *,
    report_payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    """Validate a supplement against the exact seven report bytes it cites."""

    if set(value) != _TOP_LEVEL_KEYS:
        raise ValueError("empirical_hardening_supplement_schema_invalid")
    reports = _ordered_report_payloads(report_payloads)
    envelope = empirical_research_reports.validate_report_bundle(reports)
    candidate = dict(value)
    supplement_id = str(candidate.pop("supplement_id", ""))
    if supplement_id != _sha256(canonical_supplement_bytes(candidate)):
        raise ValueError("empirical_hardening_supplement_id_invalid")
    if (
        candidate.get("schema_id") != SCHEMA_ID
        or candidate.get("schema_version") != SCHEMA_VERSION
        or candidate.get("status") != "descriptive_hardening_supplement"
        or candidate.get("partitions") != list(SELECTION_PARTITIONS)
        or candidate.get("partition_policy")
        != "development_and_validation_only"
        or candidate.get("holdout_accessed") is not False
        or candidate.get("final_test_data_accessed") is not False
        or candidate.get("raw_final_test_run_accessed") is not False
        or candidate.get("sealed_v1_report_summaries_used_for_operator_display_only")
        is not True
        or candidate.get("research_only") is not True
        or candidate.get("auto_apply") is not False
        or candidate.get("policy_eligible") is not False
        or candidate.get("safety") != _ZERO_SAFETY
    ):
        raise ValueError("empirical_hardening_supplement_contract_invalid")
    expected_report_binding = _report_binding(envelope, reports)
    report_binding = candidate.get("v1_report_bundle")
    if (
        not isinstance(report_binding, Mapping)
        or set(report_binding) != _REPORT_BINDING_KEYS
        or report_binding != expected_report_binding
    ):
        raise ValueError("empirical_hardening_supplement_report_binding_invalid")
    selection = candidate.get("selection_run")
    expected_selection = envelope.get("selection_run")
    if (
        not isinstance(selection, Mapping)
        or set(selection) != _SELECTION_BINDING_KEYS
        or not isinstance(expected_selection, Mapping)
    ):
        raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    for field in (
        "run_fingerprint",
        "protocol_version",
        "protocol_sha256",
        "input_sha256",
        "code_sha256",
        "configuration_sha256",
        "manifest_sha256",
        "artifact_sha256",
    ):
        if selection.get(field) != expected_selection.get(field):
            raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    selection_artifacts = selection.get("artifact_sha256")
    if (
        not isinstance(selection_artifacts, Mapping)
        or not isinstance(expected_selection.get("artifact_sha256"), Mapping)
        or set(selection_artifacts) != set(expected_selection["artifact_sha256"])
        or any(
            not _safe_leaf_name(name)
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            for name, digest in selection_artifacts.items()
        )
        or any(
            not isinstance(selection.get(field), str)
            or not _SHA256.fullmatch(selection[field])
            for field in (
                "run_fingerprint",
                "protocol_sha256",
                "input_sha256",
                "code_sha256",
                "configuration_sha256",
                "manifest_sha256",
            )
        )
    ):
        raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    if (
        selection.get("partitions") != list(SELECTION_PARTITIONS)
        or selection.get("holdout_accessed") is not False
        or selection.get("final_test_data_accessed") is not False
        or selection.get("immutable") is not True
    ):
        raise ValueError("empirical_hardening_supplement_selection_scope_invalid")
    _validate_algorithm_contract(candidate.get("diagnostics_algorithm_contract"))
    calibration = candidate.get("route_conditioned_calibration")
    risk = candidate.get("market_wide_risk_diagnostics")
    if not isinstance(calibration, Mapping) or not isinstance(risk, Mapping):
        raise ValueError("empirical_hardening_supplement_diagnostic_missing")
    observed_calibration = (
        empirical_report_diagnostics.validate_route_conditioned_calibration(
            calibration,
            source_run_fingerprint=str(selection.get("run_fingerprint") or ""),
        )
    )
    observed_risk = empirical_report_diagnostics.validate_market_wide_risk_diagnostics(
        risk,
        source_run_fingerprint=str(selection.get("run_fingerprint") or ""),
    )
    if observed_calibration != dict(calibration) or observed_risk != dict(risk):
        raise ValueError("empirical_hardening_supplement_diagnostic_invalid")
    validation = _json_mapping(
        reports[empirical_research_reports.REPORT_FILENAMES[1]],
        name=empirical_research_reports.REPORT_FILENAMES[1],
    )
    policy = _json_mapping(
        reports[empirical_research_reports.REPORT_FILENAMES[5]],
        name=empirical_research_reports.REPORT_FILENAMES[5],
    )
    if candidate.get("operator_summary") != _operator_summary(validation, policy):
        raise ValueError("empirical_hardening_supplement_operator_summary_invalid")
    return {**candidate, "supplement_id": supplement_id}


def validate_supplement(
    value: Mapping[str, Any],
    *,
    report_payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    """Public concise alias for read-only dashboard and report consumers."""

    return validate_hardening_supplement(value, report_payloads=report_payloads)


def parse_and_validate_hardening_supplement(
    payload: bytes,
    *,
    report_payloads: Mapping[str, bytes],
) -> dict[str, Any]:
    if not payload or len(payload) > MAX_SUPPLEMENT_BYTES:
        raise ValueError("empirical_hardening_supplement_size_invalid")
    value = _json_mapping(payload, name=SUPPLEMENT_FILENAME)
    if canonical_supplement_bytes(value) != payload:
        raise ValueError("empirical_hardening_supplement_noncanonical")
    return validate_hardening_supplement(value, report_payloads=report_payloads)


def _prepare(
    *,
    selection_run: str | Path,
    report_dir: str | Path,
    report_anchor: _DirectoryAnchor | None = None,
) -> _PreparedSupplement:
    if report_anchor is None:
        with _anchored_directory(report_dir) as opened:
            return _prepare(
                selection_run=selection_run,
                report_dir=report_dir,
                report_anchor=opened,
            )
    reports = _read_reports(report_anchor)
    envelope = empirical_research_reports.validate_report_bundle(reports)
    manifest, artifacts = _load_verified_selection_run(selection_run, envelope)
    selection_binding = _selection_binding(manifest, artifacts, envelope)
    idea_rows = empirical_replay_persistence.decode_archive_rows(
        empirical_replay_persistence.IDEA_INDEX_FILENAME,
        artifacts,
    )
    episode_rows = empirical_replay_persistence.decode_archive_rows(
        empirical_replay_persistence.EPISODE_INDEX_FILENAME,
        artifacts,
    )
    fingerprint = str(manifest["run_fingerprint"])
    calibration = empirical_report_diagnostics.build_route_conditioned_calibration(
        idea_rows,
        episode_rows,
        source_run_fingerprint=fingerprint,
    )
    risk = empirical_report_diagnostics.build_market_wide_risk_diagnostics(
        idea_rows,
        episode_rows,
        source_run_fingerprint=fingerprint,
    )
    validation = _json_mapping(
        reports[empirical_research_reports.REPORT_FILENAMES[1]],
        name=empirical_research_reports.REPORT_FILENAMES[1],
    )
    policy = _json_mapping(
        reports[empirical_research_reports.REPORT_FILENAMES[5]],
        name=empirical_research_reports.REPORT_FILENAMES[5],
    )
    core: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "descriptive_hardening_supplement",
        "v1_report_bundle": _report_binding(envelope, reports),
        "selection_run": selection_binding,
        "partitions": list(SELECTION_PARTITIONS),
        "partition_policy": "development_and_validation_only",
        "holdout_accessed": False,
        "final_test_data_accessed": False,
        "raw_final_test_run_accessed": False,
        "sealed_v1_report_summaries_used_for_operator_display_only": True,
        "operator_summary": _operator_summary(validation, policy),
        "route_conditioned_calibration": calibration,
        "market_wide_risk_diagnostics": risk,
        "diagnostics_algorithm_contract": _diagnostics_algorithm_contract(),
        "research_only": True,
        "auto_apply": False,
        "policy_eligible": False,
        "safety": dict(_ZERO_SAFETY),
    }
    value = {
        **core,
        "supplement_id": _sha256(canonical_supplement_bytes(core)),
    }
    payload = canonical_supplement_bytes(value)
    if len(payload) > MAX_SUPPLEMENT_BYTES:
        raise ValueError("empirical_hardening_supplement_size_invalid")
    validate_hardening_supplement(value, report_payloads=reports)
    return _PreparedSupplement(
        report_dir=report_anchor.path,
        report_payloads=reports,
        report_sha256={name: _sha256(data) for name, data in reports.items()},
        value=value,
        payload=payload,
    )


def _read_reports(anchor: _DirectoryAnchor) -> dict[str, bytes]:
    reports = {
        name: _read_regular_leaf(
            anchor.fd,
            name,
            maximum=empirical_research_reports.MAX_REPORT_BYTES,
        )
        for name in empirical_research_reports.REPORT_FILENAMES
    }
    _assert_anchor_current(anchor)
    return _ordered_report_payloads(reports)


def _assert_reports_current(
    anchor: _DirectoryAnchor,
    prepared: _PreparedSupplement,
) -> None:
    _assert_anchor_current(anchor)
    observed = _read_reports(anchor)
    if observed != prepared.report_payloads or {
        name: _sha256(payload) for name, payload in observed.items()
    } != prepared.report_sha256:
        raise RuntimeError("empirical_hardening_supplement_report_drift")
    empirical_research_reports.validate_report_bundle(observed)


def _validate_bound_output(
    anchor: _DirectoryAnchor,
    prepared: _PreparedSupplement,
) -> None:
    _assert_reports_current(anchor, prepared)
    payload = _read_regular_leaf(
        anchor.fd,
        SUPPLEMENT_FILENAME,
        maximum=MAX_SUPPLEMENT_BYTES,
    )
    if payload != prepared.payload:
        raise RuntimeError("empirical_hardening_supplement_post_write_drift")
    parse_and_validate_hardening_supplement(
        payload,
        report_payloads=prepared.report_payloads,
    )
    _assert_anchor_current(anchor)


def _load_verified_selection_run(
    selection_run: str | Path,
    envelope: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Preflight selection scope before reading any non-manifest leaf."""

    expected = envelope.get("selection_run")
    if not isinstance(expected, Mapping):
        raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    expected_fingerprint = str(expected.get("run_fingerprint") or "")
    if not _SHA256.fullmatch(expected_fingerprint):
        raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    absolute = _absolute_path(selection_run)
    if absolute.name != expected_fingerprint:
        raise ValueError("empirical_hardening_supplement_selection_leaf_invalid")

    with _anchored_directory(absolute) as anchor:
        manifest_payload = _read_regular_leaf(
            anchor.fd,
            empirical_replay_store.MANIFEST_FILENAME,
            maximum=MAX_MANIFEST_BYTES,
        )
        if _sha256(manifest_payload) != expected.get("manifest_sha256"):
            raise ValueError(
                "empirical_hardening_supplement_selection_manifest_invalid"
            )
        manifest = _json_mapping(
            manifest_payload,
            name=empirical_replay_store.MANIFEST_FILENAME,
        )
        if empirical_replay_store.canonical_json_bytes(manifest) != manifest_payload:
            raise ValueError(
                "empirical_hardening_supplement_selection_manifest_noncanonical"
            )

        config = manifest.get("configuration")
        if not isinstance(config, Mapping) or (
            config.get("mode") != "full"
            or config.get("data_mode") != "full"
            or config.get("partitions") != list(SELECTION_PARTITIONS)
            or config.get("universe_top_n") != 100
        ):
            raise ValueError(
                "empirical_hardening_supplement_selection_scope_invalid"
            )
        configuration_sha256 = _sha256(
            empirical_replay_store.canonical_json_bytes(config)
        )
        for field in (
            "run_fingerprint",
            "protocol_version",
            "protocol_sha256",
            "input_sha256",
            "code_sha256",
        ):
            if manifest.get(field) != expected.get(field):
                raise ValueError(
                    "empirical_hardening_supplement_selection_binding_invalid"
                )
        if configuration_sha256 != expected.get("configuration_sha256"):
            raise ValueError(
                "empirical_hardening_supplement_selection_binding_invalid"
            )

        descriptors = manifest.get("artifacts")
        expected_artifacts = expected.get("artifact_sha256")
        if (
            not isinstance(descriptors, Mapping)
            or not descriptors
            or len(descriptors) > MAX_SELECTION_ARTIFACTS
            or not isinstance(expected_artifacts, Mapping)
            or not set(expected_artifacts) <= set(descriptors)
        ):
            raise ValueError(
                "empirical_hardening_supplement_selection_artifacts_invalid"
            )
        total = 0
        for name, descriptor in descriptors.items():
            if not _safe_leaf_name(name) or not isinstance(descriptor, Mapping):
                raise ValueError(
                    "empirical_hardening_supplement_selection_artifacts_invalid"
                )
            if set(descriptor) != {"sha256", "size_bytes"}:
                raise ValueError(
                    "empirical_hardening_supplement_selection_artifacts_invalid"
                )
            digest = descriptor.get("sha256")
            size = descriptor.get("size_bytes")
            if (
                not isinstance(digest, str)
                or not _SHA256.fullmatch(digest)
                or (
                    name in expected_artifacts
                    and digest != expected_artifacts.get(name)
                )
                or type(size) is not int
                or size < 0
                or size > empirical_replay_store.MAX_ARTIFACT_BYTES
            ):
                raise ValueError(
                    "empirical_hardening_supplement_selection_artifacts_invalid"
                )
            total += size
        if total > empirical_replay_store.MAX_BUNDLE_BYTES:
            raise ValueError(
                "empirical_hardening_supplement_selection_artifacts_invalid"
            )

        names = _directory_names(anchor.fd, maximum=MAX_SELECTION_ARTIFACTS + 1)
        expected_names = {
            empirical_replay_store.MANIFEST_FILENAME,
            *descriptors,
        }
        if set(names) != expected_names:
            raise RuntimeError(
                "empirical_hardening_supplement_selection_artifact_set_drift"
            )
        payloads = {empirical_replay_store.MANIFEST_FILENAME: manifest_payload}
        for name in sorted(descriptors):
            descriptor = descriptors[name]
            payload = _read_regular_leaf(
                anchor.fd,
                name,
                maximum=empirical_replay_store.MAX_ARTIFACT_BYTES,
            )
            if (
                len(payload) != descriptor["size_bytes"]
                or _sha256(payload) != descriptor["sha256"]
            ):
                raise RuntimeError(
                    "empirical_hardening_supplement_selection_artifact_drift"
                )
            payloads[name] = payload
        errors = empirical_replay_store.validate_manifest(
            manifest,
            payloads,
            expected_run_fingerprint=expected_fingerprint,
        )
        if errors:
            raise RuntimeError(
                "empirical_hardening_supplement_selection_manifest_invalid:"
                + ";".join(errors)
            )
        _assert_anchor_current(anchor)
        return manifest, payloads


def _selection_binding(
    manifest: Mapping[str, Any],
    artifacts: Mapping[str, bytes],
    envelope: Mapping[str, Any],
) -> dict[str, Any]:
    config = manifest.get("configuration")
    if not isinstance(config, Mapping) or (
        config.get("mode") != "full"
        or config.get("data_mode") != "full"
        or config.get("partitions") != list(SELECTION_PARTITIONS)
        or config.get("universe_top_n") != 100
    ):
        raise ValueError("empirical_hardening_supplement_selection_scope_invalid")
    expected = envelope.get("selection_run")
    if not isinstance(expected, Mapping):
        raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    manifest_payload = artifacts.get(empirical_replay_store.MANIFEST_FILENAME)
    if not isinstance(manifest_payload, bytes):
        raise ValueError("empirical_hardening_supplement_selection_manifest_missing")
    manifest_artifacts = manifest.get("artifacts")
    expected_artifacts = expected.get("artifact_sha256")
    if not isinstance(manifest_artifacts, Mapping) or not isinstance(
        expected_artifacts, Mapping
    ) or not set(expected_artifacts) <= set(manifest_artifacts):
        raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    observed_artifacts: dict[str, str] = {}
    for name in sorted(expected_artifacts):
        row = manifest_artifacts[name]
        if (
            not _safe_leaf_name(name)
            or not isinstance(row, Mapping)
            or set(row) != {"sha256", "size_bytes"}
            or not isinstance(row.get("sha256"), str)
            or not _SHA256.fullmatch(row["sha256"])
        ):
            raise ValueError(
                "empirical_hardening_supplement_selection_binding_invalid"
            )
        observed_artifacts[name] = row["sha256"]
    required_indices = {
        empirical_replay_persistence.IDEA_INDEX_FILENAME,
        empirical_replay_persistence.EPISODE_INDEX_FILENAME,
    }
    if (
        observed_artifacts != dict(expected_artifacts)
        or not required_indices <= set(observed_artifacts)
        or "final_test_confirmation.json" in manifest_artifacts
    ):
        raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    binding = {
        "run_fingerprint": str(manifest.get("run_fingerprint") or ""),
        "protocol_version": str(manifest.get("protocol_version") or ""),
        "protocol_sha256": str(manifest.get("protocol_sha256") or ""),
        "input_sha256": str(manifest.get("input_sha256") or ""),
        "code_sha256": str(manifest.get("code_sha256") or ""),
        "configuration_sha256": _sha256(
            empirical_replay_store.canonical_json_bytes(config)
        ),
        "manifest_sha256": _sha256(manifest_payload),
        "artifact_sha256": observed_artifacts,
        "partitions": list(SELECTION_PARTITIONS),
        "holdout_accessed": False,
        "final_test_data_accessed": False,
        "immutable": True,
    }
    for field in (
        "run_fingerprint",
        "protocol_version",
        *_DIGEST_FIELDS,
        "artifact_sha256",
    ):
        if binding.get(field) != expected.get(field):
            raise ValueError("empirical_hardening_supplement_selection_binding_invalid")
    return binding


def _report_binding(
    envelope: Mapping[str, Any],
    reports: Mapping[str, bytes],
) -> dict[str, Any]:
    return {
        "bundle_id": str(envelope.get("bundle_id") or ""),
        "protocol_version": str(envelope.get("protocol_version") or ""),
        "protocol_sha256": str(envelope.get("protocol_sha256") or ""),
        "report_artifacts": list(empirical_research_reports.REPORT_FILENAMES),
        "report_sha256": {
            name: _sha256(reports[name])
            for name in empirical_research_reports.REPORT_FILENAMES
        },
        "report_count": len(empirical_research_reports.REPORT_FILENAMES),
        "immutable": True,
    }


def _diagnostics_algorithm_contract() -> dict[str, Any]:
    component_sha256: dict[str, str] = {}
    for name, path_value in sorted(_ALGORITHM_COMPONENTS.items()):
        supplied = path_value()
        if supplied is None:
            raise RuntimeError(
                "empirical_hardening_supplement_algorithm_source_unavailable"
            )
        component_sha256[name] = _sha256(
            _read_absolute_regular_file(
                Path(supplied),
                maximum=MAX_SOURCE_COMPONENT_BYTES,
            )
        )
    core: dict[str, Any] = {
        "schema_id": DIAGNOSTICS_ALGORITHM_CONTRACT_SCHEMA_ID,
        "schema_version": DIAGNOSTICS_ALGORITHM_CONTRACT_SCHEMA_VERSION,
        "diagnostic_schema_version": empirical_report_diagnostics.SCHEMA_VERSION,
        "route_calibration_schema_id": (
            empirical_report_diagnostics.ROUTE_CALIBRATION_SCHEMA_ID
        ),
        "market_risk_schema_id": empirical_report_diagnostics.MARKET_RISK_SCHEMA_ID,
        "selection_partitions": list(SELECTION_PARTITIONS),
        "component_sha256": component_sha256,
    }
    return {
        **core,
        "contract_digest": _sha256(
            empirical_replay_store.canonical_json_bytes(core)
        ),
    }


def _validate_algorithm_contract(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != _ALGORITHM_CONTRACT_KEYS:
        raise ValueError(
            "empirical_hardening_supplement_algorithm_contract_invalid"
        )
    candidate = dict(value)
    digest = candidate.pop("contract_digest", None)
    components = candidate.get("component_sha256")
    if (
        not isinstance(digest, str)
        or not _SHA256.fullmatch(digest)
        or digest
        != _sha256(empirical_replay_store.canonical_json_bytes(candidate))
        or not isinstance(components, Mapping)
        or set(components) != set(_ALGORITHM_COMPONENTS)
        or any(
            not isinstance(item, str) or not _SHA256.fullmatch(item)
            for item in components.values()
        )
        or dict(value) != _diagnostics_algorithm_contract()
    ):
        raise ValueError(
            "empirical_hardening_supplement_algorithm_contract_invalid"
        )


def _publish_supplement_no_clobber(
    anchor: _DirectoryAnchor,
    prepared: _PreparedSupplement,
) -> None:
    empirical_hardening_io.publish_regular_leaf_no_clobber(
        anchor,
        name=SUPPLEMENT_FILENAME,
        payload=prepared.payload,
        maximum=MAX_SUPPLEMENT_BYTES,
        guard=lambda: _assert_reports_current(anchor, prepared),
    )


def _operator_summary(
    validation: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    conclusions = _required_mapping(
        validation.get("conclusions"),
        "empirical_hardening_supplement_conclusions_missing",
    )
    recommendations, aggregate = _policy_summary_inputs(policy)
    route_findings = _required_mapping(
        conclusions.get("route_findings"),
        "empirical_hardening_supplement_route_findings_missing",
    )
    burden = _optional_mapping(aggregate.get("operator_burden"))
    regime_stability = aggregate.get("regime_stability")
    regime_stability = _optional_mapping(regime_stability)
    spread_observed, cost_bases = _operator_cost_values(conclusions)
    violation_count = _operator_monotonicity_violations(conclusions)
    regime_status = _regime_status(conclusions, regime_stability)
    route_gaps = list(conclusions.get("routes_with_no_empirical_evidence") or [])
    origin_gaps = list(conclusions.get("origins_with_no_empirical_evidence") or [])
    missing_data = list(conclusions.get("additional_data_most_needed") or [])
    negative_result = (
        conclusions.get("production_policy_unchanged") is True
        and not any(row.get("status") == "candidate" for row in recommendations)
    )
    return {
        "result": "no_supported_policy_change" if negative_result else "human_review_required",
        "negative_conclusion": negative_result,
        "final_confirmation_status": str(
            conclusions.get("final_confirmation_status") or "unavailable"
        ),
        "current_policy_aggregate": {
            **_operator_aggregate_values(aggregate),
        },
        "shadow_alternative_count": len(recommendations),
        "unsupported_shadow_alternative_count": sum(
            row.get("status") == "not_supported" for row in recommendations
        ),
        "route_level_result": {
            route: _route_summary(route_findings.get(route))
            for route in ("risk_watch", "dashboard_watch")
        },
        "regime_dependence": regime_status,
        "regime_summary": {
            "status": regime_status,
            "comparable_regime_count": regime_stability.get(
                "comparable_regime_count"
            ),
            "multiple_comparison_warning": regime_stability.get(
                "multiple_comparison_warning"
            ),
        },
        "historical_spread_observed": spread_observed,
        "cost_basis": cost_bases[0] if len(cost_bases) == 1 else "mixed_or_unavailable",
        "cost_summary": {
            "historical_spread_observed": spread_observed,
            "cost_bases": cost_bases,
            "interpretation": "assumed_sensitivity_not_execution_evidence",
        },
        "score_monotonicity_violation_count": violation_count,
        "score_monotonicity_interpretation": "descriptive_only_no_automatic_retuning",
        "score_monotonicity_summary": {
            "violation_count": violation_count,
            "probabilistic_calibration_claim": False,
            "automatic_retuning": False,
        },
        "maximum_urgent_items_on_one_day": burden.get(
            "maximum_urgent_items_on_one_day"
        ),
        "operator_burden_summary": {
            "maximum_urgent_items_on_one_day": burden.get(
                "maximum_urgent_items_on_one_day"
            ),
            "ideas_per_observed_day": burden.get("ideas_per_observed_day"),
            "urgent_item_count": burden.get("urgent_item_count"),
        },
        "routes_with_no_empirical_evidence": route_gaps,
        "origins_with_no_empirical_evidence": origin_gaps,
        "evidence_gap_summary": {
            "route_count": len(route_gaps),
            "origin_count": len(origin_gaps),
        },
        "missing_data": missing_data,
        "live_status": _operator_live_status(validation),
        "production_policy_unchanged": conclusions.get("production_policy_unchanged")
        is True,
        "automatic_policy_application": False,
    }


def _policy_summary_inputs(
    policy: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
    simulation = policy.get("selection_simulation")
    confirmation = policy.get("final_test_confirmation")
    if not isinstance(simulation, Mapping) or not isinstance(confirmation, Mapping):
        raise ValueError("empirical_hardening_supplement_policy_summary_missing")
    recommendations = [
        row for row in simulation.get("recommendations", []) if isinstance(row, Mapping)
    ]
    production = next(
        (
            row
            for row in confirmation.get("evaluated_scenarios", [])
            if isinstance(row, Mapping) and row.get("scenario") == "production_policy"
        ),
        {},
    )
    return recommendations, _optional_mapping(production)


def _operator_cost_values(
    conclusions: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    costs = _optional_mapping(conclusions.get("cost_and_survivability"))
    rows = [
        row["cost_sensitivity"]
        for row in costs.values()
        if isinstance(row, Mapping)
        and isinstance(row.get("cost_sensitivity"), Mapping)
    ]
    return (
        any(row.get("historical_spread_observed") is True for row in rows),
        sorted({str(row.get("cost_basis") or "unknown") for row in rows}),
    )


def _operator_monotonicity_violations(conclusions: Mapping[str, Any]) -> int:
    monotonicity = _optional_mapping(conclusions.get("score_monotonicity"))
    return sum(
        int(row.get("violation_count") or 0)
        for row in monotonicity.values()
        if isinstance(row, Mapping)
    )


def _operator_aggregate_values(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scenario": str(aggregate.get("scenario") or "production_policy"),
        "episode_count": aggregate.get("episode_count"),
        "matured_visible_episode_count": aggregate.get("matured_visible_episode_count"),
        "mean_directional_return_fraction": aggregate.get(
            "mean_directional_return_fraction"
        ),
        "hit_rate": aggregate.get("hit_rate"),
        "quick_failure_rate": aggregate.get("quick_failure_rate"),
        "evidence_strength": aggregate.get("evidence_strength"),
    }


def _operator_live_status(validation: Mapping[str, Any]) -> dict[str, Any]:
    bundle = _optional_mapping(validation.get("bundle"))
    binding = _optional_mapping(bundle.get("live_campaign_report"))
    projection = _optional_mapping(binding.get("canonical_projection"))
    scorecard = _optional_mapping(projection.get("scorecard"))
    return {
        "binding_status": str(binding.get("status") or "not_provided"),
        "campaign_status": str(projection.get("campaign_status") or "not_available"),
        "evidence_strength": str(
            projection.get("evidence_strength") or "not_available"
        ),
        "policy_conclusion": str(
            scorecard.get("policy_conclusion") or "not_available"
        ),
        "evidence_pooled_with_replay": binding.get("evidence_pooled_with_replay")
        is True,
    }


def _required_mapping(value: Any, error: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(error)
    return value


def _optional_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _regime_status(
    conclusions: Mapping[str, Any],
    production_regimes: Mapping[str, Any],
) -> str:
    rows = production_regimes.get("cohorts")
    directions = {
        1 if float(row.get("mean_directional_return_fraction")) > 0 else -1
        for row in rows
        if isinstance(rows, list)
        and isinstance(row, Mapping)
        and isinstance(row.get("mean_directional_return_fraction"), (int, float))
        and not isinstance(row.get("mean_directional_return_fraction"), bool)
    } if isinstance(rows, list) else set()
    regime_findings = conclusions.get("regime_and_data_quality")
    if not directions and isinstance(regime_findings, Mapping):
        for partition in regime_findings.values():
            cohorts = partition.get("market_regime_cohorts") if isinstance(
                partition, Mapping
            ) else None
            if not isinstance(cohorts, list):
                continue
            for row in cohorts:
                if not isinstance(row, Mapping) or not row.get("sample_size"):
                    continue
                direction = str(row.get("result_direction") or "")
                if direction.startswith("positive"):
                    directions.add(1)
                elif direction.startswith("negative"):
                    directions.add(-1)
    if len(directions) > 1:
        return "descriptive_results_vary_by_regime"
    if directions:
        return "single_direction_observed_across_available_regimes"
    return "not_evaluable"


def _route_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"evidence_status": "unavailable", "partitions": {}}
    partitions = value.get("partitions")
    partitions = partitions if isinstance(partitions, Mapping) else {}
    return {
        "evidence_status": str(value.get("evidence_status") or "unavailable"),
        "matured_episode_count": value.get("matured_episode_count"),
        "partitions": {
            name: {
                "sample_size": row.get("sample_size"),
                "result_direction": row.get("result_direction"),
                "evidence_strength": row.get("evidence_strength"),
            }
            for name, row in partitions.items()
            if isinstance(row, Mapping)
        },
    }


def _ordered_report_payloads(payloads: Mapping[str, bytes]) -> dict[str, bytes]:
    names = empirical_research_reports.REPORT_FILENAMES
    if tuple(payloads) != names:
        raise ValueError("empirical_hardening_supplement_reports_missing")
    ordered = {name: payloads[name] for name in names}
    if any(not isinstance(data, bytes) for data in ordered.values()):
        raise ValueError("empirical_hardening_supplement_reports_invalid")
    return ordered


def _json_mapping(payload: bytes, *, name: str) -> dict[str, Any]:
    try:
        value = loads_no_duplicate_keys(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"empirical_hardening_supplement_json_invalid:{name}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"empirical_hardening_supplement_json_invalid:{name}")
    return dict(value)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write/check a separately attested empirical hardening supplement."
    )
    parser.add_argument("--selection-run", required=True)
    parser.add_argument("--report-dir", default="research")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    result = write_hardening_supplement(
        selection_run=args.selection_run,
        report_dir=args.report_dir,
        check=args.check,
    )
    status = "checked" if result.checked else "resumed" if result.resumed else "written"
    if args.as_json:
        print(
            json.dumps(
                {
                    "status": status,
                    "filename": SUPPLEMENT_FILENAME,
                    "supplement_id": result.supplement_id,
                    "size_bytes": len(result.payload),
                    "research_only": True,
                },
                sort_keys=True,
            )
        )
    else:
        print(
            f"empirical_hardening_supplement={status} "
            f"id={result.supplement_id} bytes={len(result.payload)}"
        )
    return 0


__all__ = (
    "HardeningSupplementResult",
    "DIAGNOSTICS_ALGORITHM_CONTRACT_SCHEMA_ID",
    "DIAGNOSTICS_ALGORITHM_CONTRACT_SCHEMA_VERSION",
    "MAX_MANIFEST_BYTES",
    "MAX_SUPPLEMENT_BYTES",
    "SCHEMA_ID",
    "SCHEMA_VERSION",
    "SELECTION_PARTITIONS",
    "SUPPLEMENT_FILENAME",
    "build_hardening_supplement",
    "canonical_supplement_bytes",
    "main",
    "parse_and_validate_hardening_supplement",
    "validate_supplement",
    "validate_hardening_supplement",
    "write_hardening_supplement",
)


if __name__ == "__main__":
    raise SystemExit(main())
