"""Separately attested empirical hardening supplement regressions."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import (
    empirical_hardening_supplement as supplement,
    empirical_replay_persistence,
    empirical_replay_store,
    empirical_research_reports,
)


_RUN = "a" * 64
_PROTOCOL = "b" * 64
_INPUT = "c" * 64
_CODE = "d" * 64
_BUNDLE = "e" * 64


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _resign(value: dict) -> None:
    core = {key: item for key, item in value.items() if key != "supplement_id"}
    value["supplement_id"] = _sha(
        empirical_replay_store.canonical_json_bytes(core)
    )


def _validation_report() -> dict:
    return {
        "conclusions": {
            "production_policy_unchanged": True,
            "final_confirmation_status": "no_candidate_recommendations",
            "route_findings": {
                "risk_watch": {
                    "evidence_status": "historical_descriptive_evidence",
                    "matured_episode_count": 30,
                    "partitions": {
                        "development": {
                            "sample_size": 10,
                            "result_direction": "negative_descriptive",
                            "evidence_strength": "exploratory",
                        },
                        "validation": {
                            "sample_size": 20,
                            "result_direction": "negative_descriptive",
                            "evidence_strength": "exploratory",
                        },
                    },
                },
                "dashboard_watch": {
                    "evidence_status": "historical_descriptive_evidence",
                    "matured_episode_count": 15,
                    "partitions": {
                        "development": {
                            "sample_size": 8,
                            "result_direction": "positive_descriptive",
                            "evidence_strength": "exploratory",
                        },
                        "validation": {
                            "sample_size": 7,
                            "result_direction": "negative_descriptive",
                            "evidence_strength": "exploratory",
                        },
                    },
                },
            },
            "regime_and_data_quality": {
                "development": {
                    "market_regime_cohorts": [
                        {"result_direction": "positive_descriptive", "sample_size": 10},
                        {"result_direction": "negative_descriptive", "sample_size": 10},
                    ]
                }
            },
            "cost_and_survivability": {
                "development": {
                    "cost_sensitivity": {
                        "historical_spread_observed": False,
                        "cost_basis": "assumed_sensitivity_not_observed",
                    }
                },
                "validation": {
                    "cost_sensitivity": {
                        "historical_spread_observed": False,
                        "cost_basis": "assumed_sensitivity_not_observed",
                    }
                },
            },
            "score_monotonicity": {
                "development": {"violation_count": 2},
                "validation": {"violation_count": 4},
            },
            "routes_with_no_empirical_evidence": ["calendar_risk"],
            "origins_with_no_empirical_evidence": ["macro_led"],
            "additional_data_most_needed": [
                "observed spread and depth",
                "intraday observations",
            ],
        }
    }


def _policy_report() -> dict:
    return {
        "selection_simulation": {
            "recommendations": [
                {"scenario": "one", "status": "not_supported"},
                {"scenario": "two", "status": "not_supported"},
            ]
        },
        "final_test_confirmation": {
            "evaluated_scenarios": [
                {
                    "scenario": "production_policy",
                    "operator_burden": {"maximum_urgent_items_on_one_day": 91},
                }
            ]
        },
    }


def _diagnostic(schema_id: str, source_run_fingerprint: str) -> dict:
    core = {
        "schema_id": schema_id,
        "schema_version": 1,
        "source_run_fingerprint": source_run_fingerprint,
        "partitions": ["development", "validation"],
        "partition_policy": "development_and_validation_only",
        "research_only": True,
        "auto_apply": False,
        "policy_eligible": False,
        "safety": dict(supplement._ZERO_SAFETY),
        "rows": [{"status": "descriptive_only"}],
    }
    return {
        **core,
        "diagnostic_digest": _sha(empirical_replay_store.canonical_json_bytes(core)),
    }


def _configured_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    report_dir = tmp_path / "research"
    report_dir.mkdir()
    report_payloads: dict[str, bytes] = {}
    for index, name in enumerate(empirical_research_reports.REPORT_FILENAMES):
        if name == empirical_research_reports.REPORT_FILENAMES[1]:
            payload = empirical_replay_store.canonical_json_bytes(_validation_report())
        elif name == empirical_research_reports.REPORT_FILENAMES[5]:
            payload = empirical_replay_store.canonical_json_bytes(_policy_report())
        elif name.endswith(".json"):
            payload = empirical_replay_store.canonical_json_bytes(
                {"fixture": name, "index": index}
            )
        else:
            payload = f"# fixed v1 report {index}\n".encode()
        (report_dir / name).write_bytes(payload)
        report_payloads[name] = payload

    configuration = {
        "mode": "full",
        "data_mode": "full",
        "partitions": ["development", "validation"],
        "universe_top_n": 100,
    }
    artifact_payloads = {
        empirical_replay_persistence.IDEA_INDEX_FILENAME: b"verified-ideas-index\n",
        empirical_replay_persistence.EPISODE_INDEX_FILENAME: b"verified-episodes-index\n",
    }
    manifest = {
        "run_fingerprint": _RUN,
        "protocol_version": "decision_radar_empirical_validation_v1",
        "protocol_sha256": _PROTOCOL,
        "input_sha256": _INPUT,
        "code_sha256": _CODE,
        "configuration": configuration,
        "artifacts": {
            name: {"sha256": _sha(payload), "size_bytes": len(payload)}
            for name, payload in artifact_payloads.items()
        },
    }
    manifest_payload = empirical_replay_store.canonical_json_bytes(manifest)
    artifact_payloads[empirical_replay_store.MANIFEST_FILENAME] = manifest_payload
    artifact_sha256 = {
        name: row["sha256"] for name, row in manifest["artifacts"].items()
    }
    selection_binding = {
        "run_fingerprint": _RUN,
        "protocol_version": manifest["protocol_version"],
        "protocol_sha256": _PROTOCOL,
        "input_sha256": _INPUT,
        "code_sha256": _CODE,
        "configuration_sha256": _sha(
            empirical_replay_store.canonical_json_bytes(configuration)
        ),
        "manifest_sha256": _sha(manifest_payload),
        "artifact_sha256": artifact_sha256,
    }
    envelope = {
        "bundle_id": _BUNDLE,
        "protocol_version": manifest["protocol_version"],
        "protocol_sha256": _PROTOCOL,
        "selection_run": selection_binding,
    }
    calls = {
        "validated": 0,
        "loaded": [],
        "decoded": [],
        "diagnostics": [],
        "diagnostic_validations": [],
    }

    def validate_reports(payloads):
        calls["validated"] += 1
        assert tuple(payloads) == empirical_research_reports.REPORT_FILENAMES
        return deepcopy(envelope)

    def load_verified(path, supplied_envelope):
        calls["loaded"].append(Path(path))
        assert supplied_envelope == envelope
        return deepcopy(manifest), dict(artifact_payloads)

    idea_rows = ({"row": "idea", "partition": "development"},)
    episode_rows = ({"row": "episode", "partition": "validation"},)

    def decode(index_filename, artifacts):
        calls["decoded"].append(index_filename)
        assert artifacts[empirical_replay_store.MANIFEST_FILENAME] == manifest_payload
        if index_filename == empirical_replay_persistence.IDEA_INDEX_FILENAME:
            return idea_rows
        if index_filename == empirical_replay_persistence.EPISODE_INDEX_FILENAME:
            return episode_rows
        raise AssertionError("unexpected archive requested")

    def calibration(ideas, episodes, *, source_run_fingerprint):
        calls["diagnostics"].append(("calibration", ideas, episodes))
        return _diagnostic(
            supplement.empirical_report_diagnostics.ROUTE_CALIBRATION_SCHEMA_ID,
            source_run_fingerprint,
        )

    def risk(ideas, episodes, *, source_run_fingerprint):
        calls["diagnostics"].append(("risk", ideas, episodes))
        return _diagnostic(
            supplement.empirical_report_diagnostics.MARKET_RISK_SCHEMA_ID,
            source_run_fingerprint,
        )

    diagnostic_keys = {
        "schema_id",
        "schema_version",
        "source_run_fingerprint",
        "partitions",
        "partition_policy",
        "research_only",
        "auto_apply",
        "policy_eligible",
        "safety",
        "rows",
        "diagnostic_digest",
    }

    def validate_diagnostic(value, *, source_run_fingerprint=None):
        calls["diagnostic_validations"].append(value["schema_id"])
        if set(value) != diagnostic_keys:
            raise ValueError("fixture diagnostic schema invalid")
        candidate = dict(value)
        digest = candidate.pop("diagnostic_digest")
        if (
            value["source_run_fingerprint"] != source_run_fingerprint
            or digest != _sha(empirical_replay_store.canonical_json_bytes(candidate))
        ):
            raise ValueError("fixture diagnostic digest invalid")
        return dict(value)

    monkeypatch.setattr(
        supplement.empirical_research_reports,
        "validate_report_bundle",
        validate_reports,
    )
    monkeypatch.setattr(
        supplement,
        "_load_verified_selection_run",
        load_verified,
    )
    monkeypatch.setattr(
        supplement.empirical_replay_persistence,
        "decode_archive_rows",
        decode,
    )
    monkeypatch.setattr(
        supplement.empirical_report_diagnostics,
        "build_route_conditioned_calibration",
        calibration,
    )
    monkeypatch.setattr(
        supplement.empirical_report_diagnostics,
        "build_market_wide_risk_diagnostics",
        risk,
    )
    monkeypatch.setattr(
        supplement.empirical_report_diagnostics,
        "validate_route_conditioned_calibration",
        validate_diagnostic,
    )
    monkeypatch.setattr(
        supplement.empirical_report_diagnostics,
        "validate_market_wide_risk_diagnostics",
        validate_diagnostic,
    )
    return {
        "report_dir": report_dir,
        "selection_run": tmp_path / "selection-run",
        "report_payloads": report_payloads,
        "manifest": manifest,
        "artifacts": artifact_payloads,
        "envelope": envelope,
        "calls": calls,
    }


def test_build_is_deterministic_bound_and_development_validation_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    first = supplement.build_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )
    second = supplement.build_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )

    assert first == second
    assert first["schema_id"] == supplement.SCHEMA_ID
    assert first["v1_report_bundle"]["bundle_id"] == _BUNDLE
    assert first["v1_report_bundle"]["report_count"] == 7
    assert first["v1_report_bundle"]["report_sha256"] == {
        name: _sha(payload)
        for name, payload in configured["report_payloads"].items()
    }
    assert first["selection_run"]["run_fingerprint"] == _RUN
    assert first["selection_run"]["artifact_sha256"] == configured[
        "envelope"
    ]["selection_run"]["artifact_sha256"]
    assert first["partitions"] == ["development", "validation"]
    assert first["holdout_accessed"] is False
    assert first["final_test_data_accessed"] is False
    assert first["raw_final_test_run_accessed"] is False
    assert first["sealed_v1_report_summaries_used_for_operator_display_only"] is True
    assert first["policy_eligible"] is False
    assert set(first["safety"].values()) == {0}
    assert first["operator_summary"]["result"] == "no_supported_policy_change"
    assert first["operator_summary"]["unsupported_shadow_alternative_count"] == 2
    assert first["operator_summary"]["maximum_urgent_items_on_one_day"] == 91
    assert first["operator_summary"]["regime_dependence"] == (
        "descriptive_results_vary_by_regime"
    )
    assert first["operator_summary"]["live_status"] == {
        "binding_status": "not_provided",
        "campaign_status": "not_available",
        "evidence_strength": "not_available",
        "policy_conclusion": "not_available",
        "evidence_pooled_with_replay": False,
    }
    assert configured["calls"]["decoded"] == [
        empirical_replay_persistence.IDEA_INDEX_FILENAME,
        empirical_replay_persistence.EPISODE_INDEX_FILENAME,
    ] * 2
    assert [row[0] for row in configured["calls"]["diagnostics"]] == [
        "calibration",
        "risk",
        "calibration",
        "risk",
    ]
    assert not (configured["report_dir"] / supplement.SUPPLEMENT_FILENAME).exists()


def test_validation_rejects_report_selection_diagnostic_and_summary_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    value = supplement.build_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )

    for mutation in ("report", "selection", "diagnostic", "summary"):
        changed = deepcopy(value)
        if mutation == "report":
            changed["v1_report_bundle"]["bundle_id"] = "0" * 64
        elif mutation == "selection":
            changed["selection_run"]["run_fingerprint"] = "0" * 64
        elif mutation == "diagnostic":
            changed["route_conditioned_calibration"]["rows"] = []
        else:
            changed["operator_summary"]["production_policy_unchanged"] = False
        core = {key: item for key, item in changed.items() if key != "supplement_id"}
        changed["supplement_id"] = _sha(
            empirical_replay_store.canonical_json_bytes(core)
        )
        with pytest.raises(ValueError):
            supplement.validate_hardening_supplement(
                changed,
                report_payloads=configured["report_payloads"],
            )


@pytest.mark.parametrize(
    "mutation",
    ("top_level", "report_binding", "selection_binding", "truncated_diagnostic"),
)
def test_validation_rejects_open_or_truncated_supplement_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    changed = supplement.build_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )
    if mutation == "top_level":
        changed["unbound_extension"] = True
    elif mutation == "report_binding":
        changed["v1_report_bundle"]["unbound_extension"] = True
    elif mutation == "selection_binding":
        changed["selection_run"]["unbound_extension"] = True
    else:
        diagnostic = changed["route_conditioned_calibration"]
        diagnostic.pop("rows")
        diagnostic_core = {
            key: item
            for key, item in diagnostic.items()
            if key != "diagnostic_digest"
        }
        diagnostic["diagnostic_digest"] = _sha(
            empirical_replay_store.canonical_json_bytes(diagnostic_core)
        )
    _resign(changed)

    with pytest.raises(ValueError):
        supplement.validate_hardening_supplement(
            changed,
            report_payloads=configured["report_payloads"],
        )


def test_algorithm_contract_binds_exact_current_implementation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    value = supplement.build_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )
    contract = value["diagnostics_algorithm_contract"]
    assert contract == supplement._diagnostics_algorithm_contract()
    assert set(contract["component_sha256"]) == set(supplement._ALGORITHM_COMPONENTS)

    changed = deepcopy(value)
    changed_contract = changed["diagnostics_algorithm_contract"]
    component = next(iter(changed_contract["component_sha256"]))
    changed_contract["component_sha256"][component] = "0" * 64
    contract_core = {
        key: item
        for key, item in changed_contract.items()
        if key != "contract_digest"
    }
    changed_contract["contract_digest"] = _sha(
        empirical_replay_store.canonical_json_bytes(contract_core)
    )
    _resign(changed)
    with pytest.raises(ValueError, match="algorithm_contract_invalid"):
        supplement.validate_hardening_supplement(
            changed,
            report_payloads=configured["report_payloads"],
        )


def test_write_and_check_preserve_every_v1_byte_and_bundle_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    before = {
        name: (configured["report_dir"] / name).read_bytes()
        for name in empirical_research_reports.REPORT_FILENAMES
    }

    written = supplement.write_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )
    after_write = {
        name: (configured["report_dir"] / name).read_bytes()
        for name in empirical_research_reports.REPORT_FILENAMES
    }
    checked = supplement.write_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
        check=True,
    )
    after_check = {
        name: (configured["report_dir"] / name).read_bytes()
        for name in empirical_research_reports.REPORT_FILENAMES
    }

    assert before == after_write == after_check
    assert written.supplement_id == checked.supplement_id
    assert written.payload == checked.payload
    assert written.checked is False and checked.checked is True
    assert configured["envelope"]["bundle_id"] == _BUNDLE
    parsed = supplement.parse_and_validate_hardening_supplement(
        written.path.read_bytes(),
        report_payloads=before,
    )
    assert parsed["supplement_id"] == written.supplement_id
    assert supplement.canonical_supplement_bytes(parsed) == written.payload
    assert supplement.validate_supplement(
        parsed,
        report_payloads=before,
    ) == parsed


def test_identical_existing_supplement_resumes_without_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    first = supplement.write_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )
    before = first.path.stat()
    second = supplement.write_hardening_supplement(
        selection_run=configured["selection_run"],
        report_dir=configured["report_dir"],
    )
    after = second.path.stat()

    assert first.resumed is False
    assert second.resumed is True
    assert first.payload == second.payload
    assert (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns) == (
        after.st_dev,
        after.st_ino,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )


def test_differing_existing_supplement_fails_without_clobber(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    output = configured["report_dir"] / supplement.SUPPLEMENT_FILENAME
    original = b"preexisting-different-supplement\n"
    output.write_bytes(original)

    with pytest.raises(RuntimeError, match="immutable_drift"):
        supplement.write_hardening_supplement(
            selection_run=configured["selection_run"],
            report_dir=configured["report_dir"],
        )

    assert output.read_bytes() == original
    assert not any(".tmp." in path.name for path in configured["report_dir"].iterdir())


def test_spliced_v1_bundle_is_rejected_before_selection_run_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    configured["calls"]["loaded"].clear()

    def reject_splice(_payloads):
        raise RuntimeError("empirical_research_report_envelope_splice")

    monkeypatch.setattr(
        supplement.empirical_research_reports,
        "validate_report_bundle",
        reject_splice,
    )
    with pytest.raises(RuntimeError, match="envelope_splice"):
        supplement.build_hardening_supplement(
            selection_run=configured["selection_run"],
            report_dir=configured["report_dir"],
        )
    assert configured["calls"]["loaded"] == []


def test_final_test_selection_run_is_rejected_before_archive_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    configured["manifest"]["configuration"]["partitions"] = ["final_test"]
    configured["calls"]["decoded"].clear()

    def load_final(_path, _envelope):
        return deepcopy(configured["manifest"]), dict(configured["artifacts"])

    monkeypatch.setattr(
        supplement,
        "_load_verified_selection_run",
        load_final,
    )
    with pytest.raises(ValueError, match="selection_scope_invalid"):
        supplement.build_hardening_supplement(
            selection_run=configured["selection_run"],
            report_dir=configured["report_dir"],
        )
    assert configured["calls"]["decoded"] == []


def test_real_final_test_preflight_reads_only_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir = tmp_path / _RUN
    run_dir.mkdir()
    artifact = b"must-not-be-read\n"
    artifact_name = empirical_replay_persistence.IDEA_INDEX_FILENAME
    configuration = {
        "mode": "full",
        "data_mode": "full",
        "partitions": ["final_test"],
        "universe_top_n": 100,
    }
    manifest = {
        "run_fingerprint": _RUN,
        "protocol_version": "decision_radar_empirical_validation_v1",
        "protocol_sha256": _PROTOCOL,
        "input_sha256": _INPUT,
        "code_sha256": _CODE,
        "configuration": configuration,
        "artifacts": {
            artifact_name: {
                "sha256": _sha(artifact),
                "size_bytes": len(artifact),
            }
        },
    }
    manifest_payload = empirical_replay_store.canonical_json_bytes(manifest)
    (run_dir / empirical_replay_store.MANIFEST_FILENAME).write_bytes(
        manifest_payload
    )
    (run_dir / artifact_name).write_bytes(artifact)
    envelope = {
        "selection_run": {
            "run_fingerprint": _RUN,
            "protocol_version": manifest["protocol_version"],
            "protocol_sha256": _PROTOCOL,
            "input_sha256": _INPUT,
            "code_sha256": _CODE,
            "configuration_sha256": _sha(
                empirical_replay_store.canonical_json_bytes(configuration)
            ),
            "manifest_sha256": _sha(manifest_payload),
            "artifact_sha256": {artifact_name: _sha(artifact)},
        }
    }
    reads: list[str] = []
    inventories: list[int] = []
    original_read = supplement._read_regular_leaf
    original_inventory = supplement._directory_names

    def recording_read(directory_fd, name, *, maximum):
        reads.append(name)
        return original_read(directory_fd, name, maximum=maximum)

    def recording_inventory(directory_fd, *, maximum):
        inventories.append(directory_fd)
        return original_inventory(directory_fd, maximum=maximum)

    monkeypatch.setattr(supplement, "_read_regular_leaf", recording_read)
    monkeypatch.setattr(supplement, "_directory_names", recording_inventory)

    with pytest.raises(ValueError, match="selection_scope_invalid"):
        supplement._load_verified_selection_run(run_dir, envelope)

    assert reads == [empirical_replay_store.MANIFEST_FILENAME]
    assert inventories == []


def test_real_selection_preflight_accepts_safe_bounded_bundle(tmp_path: Path) -> None:
    configuration = {
        "mode": "full",
        "data_mode": "full",
        "partitions": ["development", "validation"],
        "universe_top_n": 100,
    }
    artifacts = {
        empirical_replay_persistence.IDEA_INDEX_FILENAME: b"ideas\n",
        empirical_replay_persistence.EPISODE_INDEX_FILENAME: b"episodes\n",
        "unbound_but_manifest_verified.json": b"{}\n",
    }
    safety = {
        "research_only": True,
        "auto_apply": False,
        "provider_calls": 0,
        "authorization_mutations": 0,
        "telegram_sends": 0,
        "trades": 0,
        "orders": 0,
        "event_alpha_paper_trades": 0,
        "normal_rsi_writes": 0,
        "event_alpha_triggered_fade": 0,
        "dashboard_authority_mutations": 0,
    }
    stored = empirical_replay_store.write_immutable_run(
        tmp_path / "lab",
        protocol_version="decision_radar_empirical_validation_v1",
        protocol_sha256=_PROTOCOL,
        input_sha256=_INPUT,
        code_sha256=_CODE,
        configuration=configuration,
        artifacts=artifacts,
        metrics={},
        safety=safety,
    )
    manifest_payload = (
        stored.run_dir / empirical_replay_store.MANIFEST_FILENAME
    ).read_bytes()
    envelope = {
        "selection_run": {
            "run_fingerprint": stored.run_fingerprint,
            "protocol_version": stored.manifest["protocol_version"],
            "protocol_sha256": _PROTOCOL,
            "input_sha256": _INPUT,
            "code_sha256": _CODE,
            "configuration_sha256": _sha(
                empirical_replay_store.canonical_json_bytes(configuration)
            ),
            "manifest_sha256": _sha(manifest_payload),
            "artifact_sha256": {
                name: _sha(artifacts[name])
                for name in (
                    empirical_replay_persistence.IDEA_INDEX_FILENAME,
                    empirical_replay_persistence.EPISODE_INDEX_FILENAME,
                )
            },
        }
    }

    manifest, observed = supplement._load_verified_selection_run(
        stored.run_dir,
        envelope,
    )

    assert manifest == stored.manifest
    assert observed[empirical_replay_store.MANIFEST_FILENAME] == manifest_payload
    assert {name: observed[name] for name in artifacts} == artifacts


def test_selection_leaf_mismatch_rejects_before_any_leaf_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads: list[str] = []

    def reject_read(_directory_fd, name, *, maximum):
        reads.append(name)
        raise AssertionError("no leaf may be read")

    monkeypatch.setattr(supplement, "_read_regular_leaf", reject_read)
    with pytest.raises(ValueError, match="selection_leaf_invalid"):
        supplement._load_verified_selection_run(
            tmp_path / ("f" * 64),
            {"selection_run": {"run_fingerprint": _RUN}},
        )
    assert reads == []


def test_selection_intermediate_symlink_fails_before_leaf_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_parent = tmp_path / "real"
    (real_parent / _RUN).mkdir(parents=True)
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    reads: list[str] = []

    def reject_read(_directory_fd, name, *, maximum):
        reads.append(name)
        raise AssertionError("no leaf may be read")

    monkeypatch.setattr(supplement, "_read_regular_leaf", reject_read)
    with pytest.raises(RuntimeError, match="directory_unsafe"):
        supplement._load_verified_selection_run(
            linked_parent / _RUN,
            {"selection_run": {"run_fingerprint": _RUN}},
        )
    assert reads == []


def test_report_size_bound_blocks_before_selection_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    victim = configured["report_dir"] / empirical_research_reports.REPORT_FILENAMES[0]
    with victim.open("wb") as handle:
        handle.truncate(empirical_research_reports.MAX_REPORT_BYTES + 1)
    configured["calls"]["loaded"].clear()

    with pytest.raises(RuntimeError, match="leaf_size_or_type_invalid"):
        supplement.build_hardening_supplement(
            selection_run=configured["selection_run"],
            report_dir=configured["report_dir"],
        )
    assert configured["calls"]["loaded"] == []


def test_report_directory_replacement_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    report_dir = configured["report_dir"]
    moved = tmp_path / "moved-research"

    with supplement._anchored_directory(report_dir) as anchor:
        report_dir.rename(moved)
        report_dir.mkdir()
        with pytest.raises(RuntimeError, match="directory_drift"):
            supplement._assert_anchor_current(anchor)


def test_report_leaf_replacement_between_stat_and_open_is_detected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    report_dir = configured["report_dir"]
    name = empirical_research_reports.REPORT_FILENAMES[0]
    victim = report_dir / name
    original_payload = victim.read_bytes()
    replaced = report_dir / "replaced-report.old"
    original_open = supplement.empirical_hardening_io.os.open
    swapped = False

    with supplement._anchored_directory(report_dir) as anchor:
        def swapping_open(path, flags, *args, **kwargs):
            nonlocal swapped
            if (
                not swapped
                and path == name
                and kwargs.get("dir_fd") == anchor.fd
            ):
                swapped = True
                victim.rename(replaced)
                victim.write_bytes(original_payload)
            return original_open(path, flags, *args, **kwargs)

        monkeypatch.setattr(supplement.empirical_hardening_io.os, "open", swapping_open)
        with pytest.raises(RuntimeError, match="leaf_identity_invalid"):
            supplement._read_regular_leaf(
                anchor.fd,
                name,
                maximum=empirical_research_reports.MAX_REPORT_BYTES,
            )
    assert swapped is True


@pytest.mark.parametrize(
    "unsafe",
    ("root_symlink", "intermediate_symlink", "report_symlink", "supplement_symlink"),
)
def test_path_symlinks_fail_closed_without_touching_v1_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe: str,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    report_dir = configured["report_dir"]
    before = {
        name: (report_dir / name).read_bytes()
        for name in empirical_research_reports.REPORT_FILENAMES
    }
    supplied = report_dir
    if unsafe == "root_symlink":
        supplied = tmp_path / "research-link"
        supplied.symlink_to(report_dir, target_is_directory=True)
    elif unsafe == "intermediate_symlink":
        parent_link = tmp_path / "parent-link"
        parent_link.symlink_to(tmp_path, target_is_directory=True)
        supplied = parent_link / "research"
    elif unsafe == "report_symlink":
        name = empirical_research_reports.REPORT_FILENAMES[0]
        outside = tmp_path / "outside-report"
        outside.write_bytes(before[name])
        (report_dir / name).unlink()
        (report_dir / name).symlink_to(outside)
    else:
        outside = tmp_path / "outside-supplement"
        outside.write_text("do not replace")
        (report_dir / supplement.SUPPLEMENT_FILENAME).symlink_to(outside)

    with pytest.raises(RuntimeError):
        supplement.write_hardening_supplement(
            selection_run=configured["selection_run"],
            report_dir=supplied,
        )
    if unsafe != "report_symlink":
        assert {
            name: (report_dir / name).read_bytes()
            for name in empirical_research_reports.REPORT_FILENAMES
        } == before


def test_guarded_v1_hash_detects_drift_during_supplement_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _configured_inputs(tmp_path, monkeypatch)
    original = supplement._publish_supplement_no_clobber
    victim = configured["report_dir"] / empirical_research_reports.REPORT_FILENAMES[0]

    def drift_then_write(anchor, prepared):
        victim.write_bytes(b"drifted-v1-report\n")
        return original(anchor, prepared)

    monkeypatch.setattr(
        supplement,
        "_publish_supplement_no_clobber",
        drift_then_write,
    )
    with pytest.raises(RuntimeError, match="report_drift"):
        supplement.write_hardening_supplement(
            selection_run=configured["selection_run"],
            report_dir=configured["report_dir"],
        )
    assert not (configured["report_dir"] / supplement.SUPPLEMENT_FILENAME).exists()
