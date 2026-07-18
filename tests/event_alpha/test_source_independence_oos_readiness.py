from __future__ import annotations

import json
from pathlib import Path

from crypto_rsi_scanner.event_alpha.operations import source_independence_oos as oos
from crypto_rsi_scanner.event_alpha.operations import source_independence_oos_cli
from crypto_rsi_scanner.event_alpha.operations import (
    source_independence_oos_readiness as readiness,
)


def _source(
    source_id: str,
    provider: str,
    origin: str,
    body: str,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "provider": provider,
        "source_class": "publisher",
        "source_url": f"https://{origin}/{source_id}",
        "published_at": "2026-07-18T10:00:00+00:00",
        "fetched_at": "2026-07-18T10:05:00+00:00",
        "title": "Protocol governance proposal receives an independent report",
        "body": body,
    }


def _cases() -> list[dict[str, object]]:
    return [
        {
            "case_id": "case-governance-1",
            "case_category": "independently_reported_same_event",
            "event_copy_family_id": "family-governance-1",
            "source_a": _source(
                "publisher-a-1",
                "publisher_a",
                "publisher-a.example",
                "The protocol published a governance proposal with voting dates, "
                "parameters, implementation details, and a public discussion link.",
            ),
            "source_b": _source(
                "publisher-b-1",
                "publisher_b",
                "publisher-b.example",
                "An independent newsroom described the same governance vote, "
                "including its schedule, disputed parameters, and stakeholder response.",
            ),
        }
    ]


def _write_case_input(path: Path) -> None:
    path.write_text(json.dumps({"cases": _cases()}), encoding="utf-8")


def _freeze(tmp_path: Path) -> tuple[Path, Path, Path]:
    source = tmp_path / "cases.json"
    corpus = tmp_path / "corpus.json"
    template = tmp_path / "template.jsonl"
    _write_case_input(source)
    oos.export_workflow(
        input_path=source,
        corpus_output=corpus,
        template_output=template,
        split_salt="operator-stable-salt",
    )
    return source, corpus, template


def test_readiness_without_files_exposes_exact_human_input_contract() -> None:
    report = readiness.build_readiness_report()

    assert report["status"] == "case_input_required"
    assert report["configured"] == {
        "case_input": False,
        "frozen_corpus": False,
        "immutable_template": False,
        "operator_reviews": False,
        "split_salt": False,
    }
    assert report["next_action"] == "prepare_source_diverse_case_input"
    assert report["case_input_contract"]["event_copy_family_id_is_human_curated"]
    assert report["case_input_contract"]["fixtures_are_genuine_evidence"] is False
    assert report["blind_review_contract"]["algorithm_predictions_exposed"] is False
    assert report["provider_calls"] == 0
    assert report["writes"] == 0
    assert report["automatic_policy_application"] is False


def test_valid_case_input_requires_salt_then_becomes_ready_to_freeze(
    tmp_path: Path,
) -> None:
    source = tmp_path / "cases.json"
    _write_case_input(source)

    no_salt = readiness.build_readiness_report(input_path=source)
    configured = readiness.build_readiness_report(
        input_path=source,
        split_salt_configured=True,
    )

    assert no_salt["status"] == "split_salt_required"
    assert no_salt["case_input"]["case_count"] == 1
    assert no_salt["case_input"]["event_copy_family_count"] == 1
    assert no_salt["case_input"]["source_provider_count"] == 2
    assert no_salt["case_input"]["algorithm_predictions_exposed"] is False
    assert configured["status"] == "ready_to_freeze"
    assert configured["next_action"] == "freeze_corpus_and_blind_template"
    assert "event-alpha-source-independence-oos-export" in configured[
        "next_safe_command"
    ]


def test_frozen_corpus_and_template_are_ready_for_separate_human_copy(
    tmp_path: Path,
) -> None:
    _source_path, corpus, template = _freeze(tmp_path)

    report = readiness.build_readiness_report(
        corpus_path=corpus,
        template_path=template,
    )

    assert report["status"] == "ready_for_human_labels"
    assert report["frozen_corpus"]["status"] == "valid"
    assert report["frozen_corpus"]["case_count"] == 1
    assert report["immutable_template"]["status"] == "valid"
    assert report["immutable_template"]["pending_rows"] == 1
    assert report["immutable_template"]["reviewed_rows"] == 0
    assert report["next_action"] == "copy_template_and_begin_blind_review"
    assert report["protocol_v2_evidence_eligible"] is False


def test_pending_review_copy_stays_non_success_and_blind(
    tmp_path: Path,
) -> None:
    _source_path, corpus, template = _freeze(tmp_path)
    reviews = tmp_path / "reviews.jsonl"
    reviews.write_bytes(template.read_bytes())

    report = readiness.build_readiness_report(
        corpus_path=corpus,
        template_path=template,
        reviews_path=reviews,
    )

    assert report["status"] == "human_labels_pending"
    assert report["operator_reviews"]["status"] == "valid"
    assert report["operator_reviews"]["pending_rows"] == 1
    assert report["descriptive_report_readiness"]["status"] == "pending"
    assert report["blind_review_contract"]["per_case_split_assignments_exposed"] is False
    assert report["threshold_changes"] == 0
    assert report["policy_changes"] == 0


def test_immutable_template_cannot_also_be_the_editable_review_file(
    tmp_path: Path,
) -> None:
    _source_path, corpus, template = _freeze(tmp_path)

    report = readiness.build_readiness_report(
        corpus_path=corpus,
        template_path=template,
        reviews_path=template,
    )

    assert report["status"] == "invalid"
    assert report["errors"] == ["reviews_must_be_separate_template_copy"]
    assert report["operator_reviews"] == {
        "status": "invalid",
        "error": "reviews_must_be_separate_template_copy",
    }
    assert report["writes"] == 0


def test_complete_small_review_remains_coverage_incomplete_not_policy_evidence(
    tmp_path: Path,
) -> None:
    _source_path, corpus, template = _freeze(tmp_path)
    row = json.loads(template.read_text(encoding="utf-8"))
    row.update(
        {
            "review_status": "reviewed",
            "human_label": "independent",
            "reviewed_by": "human-owner",
            "reviewed_at": "2026-07-18T12:00:00+00:00",
            "review_notes": "Sources independently report the same event.",
        }
    )
    reviews = tmp_path / "reviews.jsonl"
    reviews.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

    report = readiness.build_readiness_report(
        corpus_path=corpus,
        template_path=template,
        reviews_path=reviews,
    )

    assert report["status"] == "oos_coverage_incomplete"
    assert report["operator_reviews"]["valid_reviewed_rows"] == 1
    assert report["descriptive_report_readiness"][
        "reviewed_oos_coverage_complete"
    ] is False
    assert report["descriptive_report_readiness"]["policy_conclusion"] == (
        "insufficient_for_policy_change"
    )
    assert report["next_action"] == "plan_new_independent_corpus_version"


def test_tampered_template_fails_closed_without_rendering_case_details(
    tmp_path: Path,
) -> None:
    _source_path, corpus, template = _freeze(tmp_path)
    row = json.loads(template.read_text(encoding="utf-8"))
    row["case_row_digest"] = "0" * 64
    template.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")

    report = readiness.build_readiness_report(
        corpus_path=corpus,
        template_path=template,
    )

    assert report["status"] == "invalid"
    assert report["errors"] == ["template_invalid"]
    assert report["immutable_template"]["error_codes"] == [
        "review_case_binding_mismatch"
    ]
    assert "source_a" not in report["immutable_template"]
    assert report["provider_calls"] == 0
    assert report["writes"] == 0


def test_readiness_cli_is_observational_and_returns_zero_for_missing_human_input(
    tmp_path: Path,
    capsys,
) -> None:
    before = tuple(tmp_path.iterdir())

    result = source_independence_oos_cli.main(["readiness"])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output["status"] == "case_input_required"
    assert output["provider_calls"] == 0
    assert output["writes"] == 0
    assert tuple(tmp_path.iterdir()) == before
