"""Duplicate-key rejection for exact outcome evidence JSONL readers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from crypto_rsi_scanner.event_alpha.artifacts import json_lines
from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts import context_loading
from crypto_rsi_scanner.event_alpha.operations import common, outcome_evidence
from crypto_rsi_scanner.event_alpha.outcomes import integrated_radar_outcomes
from crypto_rsi_scanner.event_alpha.radar import core_opportunity_store
from crypto_rsi_scanner.event_alpha.radar import integrated_radar


def _write_lines(path: Path, *lines: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_shared_jsonl_reader_rejects_top_level_and_nested_duplicate_keys(tmp_path):
    path = tmp_path / "evidence.jsonl"
    _write_lines(
        path,
        '{"candidate_id":"good","outcome_identity":{"run_id":"one"}}',
        '{"candidate_id":"trusted","candidate_id":"forged"}',
        '{"candidate_id":"nested","outcome_identity":{"run_id":"trusted","run_id":"forged"}}',
        '{"candidate_id":',
        '["not-an-object"]',
        "",
    )
    result = json_lines.read_jsonl(path)
    assert result.rows == ({"candidate_id": "good", "outcome_identity": {"run_id": "one"}},)
    assert result.diagnostics.total_lines == 6
    assert result.diagnostics.accepted_rows == 1
    assert result.diagnostics.duplicate_key_lines == (2, 3)
    assert result.diagnostics.invalid_json_lines == (4,)
    assert result.diagnostics.non_object_lines == (5,)
    assert result.diagnostics.blank_lines == (6,)
    assert result.diagnostics.rejected_line_count == 4
    assert result.diagnostics.read_error is False

    try:
        json_lines.loads_no_duplicate_keys('{"SECRET_ID":"trusted","SECRET_ID":"forged"}')
    except ValueError as exc:
        assert str(exc) == ""
        assert "SECRET" not in str(exc)
    else:
        raise AssertionError("duplicate object key was accepted")


def test_outcome_and_core_loaders_exclude_duplicate_identity_rows(tmp_path):
    namespace = tmp_path / "namespace"
    candidates_path = namespace / integrated_radar.INTEGRATED_CANDIDATES_FILENAME
    core_path = namespace / "event_core_opportunities.jsonl"
    outcomes_path = namespace / integrated_radar.INTEGRATED_OUTCOMES_FILENAME
    _write_lines(
        candidates_path,
        '{"candidate_id":"candidate-good","run_id":"run-good"}',
        '{"candidate_id":"candidate-trusted","candidate_id":"candidate-forged","run_id":"run-bad"}',
    )
    _write_lines(
        core_path,
        '{"row_type":"event_core_opportunity","core_opportunity_id":"core-good","run_id":"run-good","generated_at":"2026-07-12T00:00:00+00:00"}',
        '{"row_type":"event_core_opportunity","core_opportunity_id":"core-trusted","core_opportunity_id":"core-forged","run_id":"run-bad"}',
    )
    _write_lines(
        outcomes_path,
        '{"candidate_id":"candidate-good","core_opportunity_id":"core-good","run_id":"run-good"}',
        '{"candidate_id":"candidate-trusted","candidate_id":"candidate-forged","core_opportunity_id":"core-forged"}',
    )

    candidates, cores = integrated_radar_outcomes.load_integrated_radar_outcome_authority(namespace)
    outcomes = integrated_radar_outcomes.load_integrated_radar_outcomes(namespace)
    core_store = core_opportunity_store.load_core_opportunities(core_path)
    assert [row["candidate_id"] for row in candidates] == ["candidate-good"]
    assert [row["core_opportunity_id"] for row in cores] == ["core-good"]
    assert [row["candidate_id"] for row in outcomes] == ["candidate-good"]
    assert [row["core_opportunity_id"] for row in core_store.rows] == ["core-good"]


def test_operations_outcome_evidence_loader_cannot_count_duplicate_key_rows(tmp_path):
    namespace = "live_burn_in_no_send"
    base = tmp_path
    target = base / namespace
    _write_lines(
        target / integrated_radar.INTEGRATED_CANDIDATES_FILENAME,
        '{"candidate_id":"candidate-good"}',
        '{"candidate_id":"candidate-trusted","candidate_id":"candidate-forged"}',
    )
    _write_lines(
        target / "event_core_opportunities.jsonl",
        '{"core_opportunity_id":"core-good"}',
        '{"core_opportunity_id":"core-trusted","core_opportunity_id":"core-forged"}',
    )
    _write_lines(
        target / integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
        '{"candidate_id":"candidate-good","core_opportunity_id":"core-good"}',
        '{"candidate_id":"candidate-trusted","candidate_id":"candidate-forged"}',
    )

    def row_loader(base_dir, filename, *, cutoff, namespaces):
        del cutoff
        return [
            row
            for selected_namespace in namespaces
            for row in common.read_jsonl(Path(base_dir) / selected_namespace / filename)
        ]

    candidates, cores, supplied, eligible, excluded, _reasons = (
        outcome_evidence.load_exact_namespace_outcomes(
            base,
            datetime(2026, 7, 1, tzinfo=timezone.utc),
            (namespace,),
            row_loader,
            datetime(2026, 7, 12, tzinfo=timezone.utc),
        )
    )
    assert len(candidates) == 1
    assert len(cores) == 1
    assert len(supplied) == 1
    assert eligible == []
    assert len(excluded) == 1
    assert "candidate-forged" not in repr((candidates, supplied, excluded))


def test_doctor_reports_payload_free_duplicate_key_diagnostics(tmp_path):
    namespace = tmp_path / "doctor"
    candidates_path = namespace / integrated_radar.INTEGRATED_CANDIDATES_FILENAME
    _write_lines(
        candidates_path,
        '{"candidate_id":"candidate-good"}',
        '{"candidate_id":"SECRET_TRUSTED","candidate_id":"SECRET_FORGED"}',
    )
    _write_lines(
        namespace / "event_core_opportunities.jsonl",
        '{"core_opportunity_id":"core-good"}',
        '{"core_opportunity_id":"SECRET_TRUSTED","core_opportunity_id":"SECRET_FORGED"}',
    )
    _write_lines(
        namespace / integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
        '{"candidate_id":"candidate-good"}',
        '{"candidate_id":"SECRET_TRUSTED","candidate_id":"SECRET_FORGED"}',
        '{"candidate_id":',
    )
    candidate_result = json_lines.read_jsonl(candidates_path)
    diagnostics = context_loading._outcome_evidence_jsonl_diagnostics(
        namespace,
        candidate_diagnostics=candidate_result.diagnostics,
    )
    ctx = SimpleNamespace(
        outcome_evidence_jsonl_diagnostics=diagnostics,
        strict=True,
        blockers=[],
        warnings=[],
    )
    context_loading._attach_outcome_evidence_jsonl_diagnostics(ctx)
    assert ctx.warnings == []
    assert ctx.blockers == [
        "outcomes.eligibility_firewall: "
        "outcome_evidence_duplicate_json_keys=candidates:1,core:1,integrated_outcomes:1",
        "outcomes.eligibility_firewall: outcome_evidence_invalid_jsonl=integrated_outcomes:1",
    ]
    assert "SECRET_TRUSTED" not in " ".join(ctx.blockers)
    assert "SECRET_FORGED" not in " ".join(ctx.blockers)
    assert context_loading._read_jsonl(candidates_path) == [{"candidate_id": "candidate-good"}]
