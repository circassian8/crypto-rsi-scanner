"""Frozen source-independence out-of-sample research workflow regressions."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from crypto_rsi_scanner.event_alpha.operations import source_independence_oos as oos
from crypto_rsi_scanner.event_alpha.radar import source_independence


SPLIT_SALT = "declared-source-independence-study-2026-07"
SPLIT_VERSION = "source_independence_oos_split_v3"


def _long_text(prefix: str, count: int = 30) -> str:
    normalized_prefix = "".join(character for character in prefix if character.isalnum())
    return " ".join(f"{normalized_prefix}{index}" for index in range(count))


def _source(
    source_id: str,
    origin: str,
    *,
    title: str = "Market catalyst evidence report",
    body: str | None = None,
    provider: str = "public_rss",
    published_at: str = "2026-07-15T10:00:00Z",
) -> dict[str, str]:
    return {
        "source_id": source_id,
        "provider": provider,
        "source_class": "broad_news",
        "source_url": f"https://{origin}/story/{source_id}",
        "published_at": published_at,
        "fetched_at": "2026-07-15T10:05:00Z",
        "title": title,
        "body": _long_text(source_id) if body is None else body,
    }


def _case(
    case_id: str,
    *,
    category: str = "control",
    prediction: str = "independent",
    token_count: int = 30,
    family_id: str | None = None,
) -> dict[str, object]:
    common = _long_text(f"{case_id}-common-", token_count)
    if prediction == "duplicate":
        left_body = right_body = common
        left_title = right_title = "Same syndicated catalyst report"
    elif prediction == "near_duplicate":
        left_tokens = common.split()
        right_tokens = list(left_tokens)
        right_tokens[8] = "replacement"
        left_body = " ".join(left_tokens)
        right_body = " ".join(right_tokens)
        left_title = right_title = "Lightly edited catalyst report"
    elif prediction == "unassessable":
        left_body = right_body = ""
        left_title = "Tiny headline"
        right_title = "Other headline"
    else:
        left_body = _long_text(f"{case_id}-left-", token_count)
        right_body = _long_text(f"{case_id}-right-", token_count)
        left_title = "First original catalyst report"
        right_title = "Second independent catalyst report"
    return {
        "case_id": case_id,
        "case_category": category,
        "event_copy_family_id": family_id or case_id,
        "source_a": _source(
            f"{case_id}-a", "one.example", title=left_title, body=left_body
        ),
        "source_b": _source(
            f"{case_id}-b",
            "two.example",
            title=right_title,
            body=right_body,
            provider="exchange_announcement",
            published_at="2026-07-15T10:01:00Z",
        ),
    }


def _family_id_for_split(split: str, label: str) -> str:
    for index in range(100_000):
        family_id = f"{label}-{index}"
        assigned, _bucket, _digest = oos.assign_split(
            family_id,
            split_salt=SPLIT_SALT,
            split_version=SPLIT_VERSION,
        )
        if assigned == split:
            return family_id
    raise AssertionError(f"unable to find deterministic {split} family id")


def _redigest(value: dict[str, object]) -> None:
    payload = {key: child for key, child in value.items() if key != "contract_digest"}
    value["contract_digest"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _redigest_case_row(value: dict[str, object]) -> None:
    payload = {key: child for key, child in value.items() if key != "row_digest"}
    value["row_digest"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def _reviewed_rows(
    corpus: dict[str, object], labels: dict[str, str]
) -> list[dict[str, object]]:
    rows = oos.build_labeling_template_rows(corpus)
    for row in rows:
        case_id = str(row["case_id"])
        label = labels.get(case_id)
        if label is None:
            continue
        row.update(
            {
                "review_status": "reviewed",
                "human_label": label,
                "reviewed_by": "human-reviewer-1",
                "reviewed_at": "2026-07-16T09:00:00+00:00",
                "review_notes": "Compared both source texts and provenance fields.",
            }
        )
    return rows


def test_frozen_corpus_is_deterministic_and_split_uses_identity_only():
    first = _case("deterministic-one", prediction="duplicate")
    second = _case("deterministic-two", prediction="independent")

    corpus = oos.build_frozen_corpus(
        [second, first], split_salt=SPLIT_SALT, split_version=SPLIT_VERSION
    )
    reordered = oos.build_frozen_corpus(
        [first, second], split_salt=SPLIT_SALT, split_version=SPLIT_VERSION
    )

    assert corpus == reordered
    assert oos.validate_frozen_corpus(corpus) == []
    assert [row["case_id"] for row in corpus["rows"]] == [
        "deterministic-one",
        "deterministic-two",
    ]
    assert corpus["algorithm"] == source_independence.ALGORITHM
    assert corpus["split_declaration"]["split_salt"] == SPLIT_SALT
    assert corpus["split_declaration"]["split_version"] == SPLIT_VERSION
    assert corpus["split_declaration"]["assignment_unit"] == (
        "event_copy_family_id"
    )
    assert set(corpus["split_declaration"]["split_ranges"]) == {
        "development",
        "review",
        "test",
    }
    assert set(corpus["split_counts"]) == {"development", "review", "test"}
    assert corpus["research_only"] is True
    assert corpus["provider_calls"] == 0
    assert corpus["route_changes"] == 0
    assert corpus["threshold_changes"] == 0
    assert corpus["policy_changes"] == 0
    assert corpus["auto_apply"] is False

    changed = deepcopy(first)
    changed["source_b"]["body"] = _long_text("materially-changed-")
    changed_corpus = oos.build_frozen_corpus(
        [changed, second], split_salt=SPLIT_SALT, split_version=SPLIT_VERSION
    )
    before = corpus["rows"][0]
    after = changed_corpus["rows"][0]
    assert (before["split"], before["split_bucket"], before["split_assignment_digest"]) == (
        after["split"],
        after["split_bucket"],
        after["split_assignment_digest"],
    )
    assert before["case_input_digest"] != after["case_input_digest"]
    assert before["row_digest"] != after["row_digest"]

    other_salt = oos.build_frozen_corpus(
        [first, second],
        split_salt="a-different-declared-salt",
        split_version=SPLIT_VERSION,
    )
    assert corpus["split_declaration"]["declaration_digest"] != (
        other_salt["split_declaration"]["declaration_digest"]
    )
    assert corpus["rows"][0]["split_assignment_digest"] != (
        other_salt["rows"][0]["split_assignment_digest"]
    )


def test_event_copy_families_are_indivisible_and_cross_split_story_leakage_fails():
    review_family = _family_id_for_split("review", "family-review")
    test_family = _family_id_for_split("test", "family-test")
    same_family = oos.build_frozen_corpus(
        [
            _case("same-family-a", family_id=review_family),
            _case("same-family-b", family_id=review_family),
        ],
        split_salt=SPLIT_SALT,
        split_version=SPLIT_VERSION,
    )

    assert {row["split"] for row in same_family["rows"]} == {"review"}
    assert len(
        {row["split_assignment_digest"] for row in same_family["rows"]}
    ) == 1

    shared_story = _case(
        "shared-story-review",
        category="exact_syndicated_copy",
        prediction="duplicate",
        family_id=review_family,
    )
    leaked_story = _case(
        "shared-story-test",
        category="exact_syndicated_copy",
        prediction="duplicate",
        family_id=test_family,
    )
    leaked_story["source_a"] = deepcopy(shared_story["source_a"])
    leaked_story["source_b"] = deepcopy(shared_story["source_b"])
    with pytest.raises(
        oos.SourceIndependenceOOSWorkflowError,
        match="corpus_cross_split_leakage",
    ):
        oos.build_frozen_corpus(
            [shared_story, leaked_story],
            split_salt=SPLIT_SALT,
            split_version=SPLIT_VERSION,
        )

    second_review_family = _family_id_for_split("review", "family-review-second")
    same_partition_copy = deepcopy(leaked_story)
    same_partition_copy["event_copy_family_id"] = second_review_family
    valid_shared = oos.build_frozen_corpus(
        [shared_story, same_partition_copy],
        split_salt=SPLIT_SALT,
        split_version=SPLIT_VERSION,
    )
    tampered_shared = deepcopy(valid_shared)
    tampered_shared["rows"][1]["split"] = "test"
    _redigest_case_row(tampered_shared["rows"][1])
    _redigest(tampered_shared)
    shared_errors = oos.validate_frozen_corpus(tampered_shared)
    assert "corpus_source_digest_cross_split_leakage" in shared_errors
    assert "corpus_content_digest_cross_split_leakage" in shared_errors

    tampered_family = deepcopy(same_family)
    tampered_family["rows"][1]["split"] = "test"
    _redigest_case_row(tampered_family["rows"][1])
    _redigest(tampered_family)
    assert "corpus_family_cross_split_leakage" in oos.validate_frozen_corpus(
        tampered_family
    )


def test_corpus_records_exact_near_distinct_and_unassessable_predictions():
    cases = [
        _case(
            "exact-case",
            category="exact_syndicated_copy",
            prediction="duplicate",
        ),
        _case(
            "near-case",
            category="lightly_edited_cross_domain_copy",
            prediction="near_duplicate",
        ),
        _case(
            "same-event-case",
            category="independently_reported_same_event",
            prediction="independent",
        ),
        _case(
            "same-domain-update-case",
            category="same_domain_original_update",
            prediction="independent",
        ),
        _case(
            "contradiction-case",
            category="contradiction",
            prediction="independent",
        ),
        _case(
            "short-case",
            category="short_headline",
            prediction="unassessable",
        ),
        _case("control-case", category="control", prediction="independent"),
    ]
    cases[3]["source_b"]["source_url"] = (
        "https://one.example/story/same-domain-update-case-b"
    )

    corpus = oos.build_frozen_corpus(cases, split_salt=SPLIT_SALT)
    by_id = {row["case_id"]: row for row in corpus["rows"]}

    assert by_id["exact-case"]["algorithm_prediction"] == "duplicate"
    assert by_id["exact-case"]["algorithm_match_kind"] == "exact"
    assert by_id["exact-case"]["algorithm_similarity"] == 1.0
    assert by_id["exact-case"]["source_a_content_digest"] == (
        by_id["exact-case"]["source_b_content_digest"]
    )
    assert by_id["exact-case"]["source_a_digest"] != (
        by_id["exact-case"]["source_b_digest"]
    )

    assert by_id["near-case"]["algorithm_prediction"] == "duplicate"
    assert by_id["near-case"]["algorithm_match_kind"] == "near_duplicate"
    assert by_id["near-case"]["algorithm_similarity"] >= 0.8
    assert by_id["same-event-case"]["algorithm_prediction"] == "independent"
    assert by_id["same-event-case"]["algorithm_match_kind"] == "distinct"
    assert by_id["short-case"]["algorithm_prediction"] == "unassessable"
    assert by_id["short-case"]["algorithm_similarity"] is None
    assert by_id["short-case"]["source_a_assessment_status"] == "unassessable"
    assert by_id["exact-case"]["source_a_origin"] == "one.example"
    assert by_id["exact-case"]["source_b_origin"] == "two.example"
    assert by_id["same-domain-update-case"]["source_a_origin"] == "one.example"
    assert by_id["same-domain-update-case"]["source_b_origin"] == "one.example"
    assert corpus["case_category_counts"] == {
        category: 1 for category in sorted(oos.CASE_CATEGORIES)
    }
    assert by_id["exact-case"]["source_a_token_count"] >= 12
    assert by_id["short-case"]["source_a_token_count"] < 12
    assert all(len(str(row["row_digest"])) == 64 for row in corpus["rows"])


def test_label_template_is_blinded_and_review_validation_binds_provenance():
    corpus = oos.build_frozen_corpus(
        [_case("label-case", prediction="duplicate")], split_salt=SPLIT_SALT
    )
    template = oos.build_labeling_template_rows(corpus)
    row = template[0]

    for hidden in (
        "algorithm_prediction",
        "algorithm_similarity",
        "algorithm_match_kind",
        "case_category",
        "event_copy_family_id",
        "split",
        "split_bucket",
    ):
        assert hidden not in row
    assert row["review_status"] == "pending"
    assert row["human_label"] is None
    assert row["reviewed_by"] is None
    assert row["reviewed_at"] is None
    assert row["review_notes"] is None
    assert oos.validate_review_rows(corpus, template)["status"] == "valid"

    reviewed = _reviewed_rows(corpus, {"label-case": "duplicate"})
    validation = oos.validate_review_rows(corpus, reviewed)
    assert validation["status"] == "valid"
    assert validation["reviewed_rows"] == 1
    assert validation["valid_reviewed_rows"] == 1
    split = corpus["rows"][0]["split"]
    assert validation["reviewed_label_counts_by_split"][split]["duplicate"] == 1

    tampered = deepcopy(reviewed)
    tampered[0]["source_a"]["body"] = "changed after corpus freeze"
    invalid = oos.validate_review_rows(corpus, tampered)
    assert invalid["status"] == "invalid"
    assert "review_case_binding_mismatch" in invalid["errors"][0]["error_codes"]

    missing_provenance = deepcopy(reviewed)
    missing_provenance[0]["reviewed_by"] = None
    missing_provenance[0]["reviewed_at"] = "2026-07-16T09:00:00"
    missing_provenance[0]["review_notes"] = ""
    invalid = oos.validate_review_rows(corpus, missing_provenance)
    assert invalid["status"] == "invalid"
    assert set(invalid["errors"][0]["error_codes"]) >= {
        "reviewed_by_invalid",
        "reviewed_at_invalid",
        "review_notes_invalid",
    }

    missing = oos.validate_review_rows(corpus, [])
    assert missing["status"] == "invalid"
    assert missing["errors"] == [
        {
            "row_index": 0,
            "case_id": "label-case",
            "error_codes": ["review_case_missing"],
        }
    ]


def test_report_has_split_confusion_metrics_but_never_policy_eligibility():
    review_duplicate = _family_id_for_split("review", "review-duplicate")
    review_independent = _family_id_for_split("review", "review-independent")
    review_short = _family_id_for_split("review", "review-short")
    test_false_positive = _family_id_for_split("test", "test-false-positive")
    test_false_negative = _family_id_for_split("test", "test-false-negative")
    test_long = _family_id_for_split("test", "test-long")
    long_case = _case(test_long, prediction="independent", token_count=60)
    long_case["source_b"]["provider"] = "wire_service"
    long_case["source_b"]["source_class"] = "original_reporting"
    corpus = oos.build_frozen_corpus(
        [
            _case(
                review_duplicate,
                category="exact_syndicated_copy",
                prediction="duplicate",
            ),
            _case(review_independent, prediction="independent"),
            _case(
                review_short,
                category="short_headline",
                prediction="unassessable",
            ),
            _case(
                test_false_positive,
                category="exact_syndicated_copy",
                prediction="duplicate",
            ),
            _case(test_false_negative, prediction="independent"),
            long_case,
        ],
        split_salt=SPLIT_SALT,
        split_version=SPLIT_VERSION,
    )
    reviews = _reviewed_rows(
        corpus,
        {
            review_duplicate: "duplicate",
            review_independent: "independent",
            review_short: "unassessable",
            test_false_positive: "independent",
            test_false_negative: "duplicate",
            test_long: "independent",
        },
    )

    report = oos.build_descriptive_report(corpus, reviews)
    metrics = {row["split"]: row for row in report["split_metrics"]}

    assert report["status"] == "complete"
    assert set(metrics) == {"development", "review", "test"}
    assert report["reviewed_oos_coverage_complete"] is True
    assert report["oos_coverage_reasons"] == []
    assert metrics["review"]["true_positive"] == 1
    assert metrics["review"]["true_negative"] == 1
    assert metrics["review"]["precision_duplicate"] == 1.0
    assert metrics["review"]["recall_duplicate"] == 1.0
    assert metrics["test"]["false_positive"] == 1
    assert metrics["test"]["false_negative"] == 1
    assert metrics["test"]["false_merges"] == metrics["test"]["false_positive"]
    assert metrics["test"]["missed_copies"] == metrics["test"]["false_negative"]
    assert metrics["test"]["precision_duplicate"] == 0.0
    assert metrics["test"]["recall_duplicate"] == 0.0
    review_lengths = {
        row["cohort_values"][0]: row for row in metrics["review"]["text_length_cohorts"]
    }
    test_lengths = {
        row["cohort_values"][0]: row for row in metrics["test"]["text_length_cohorts"]
    }
    assert list(review_lengths) == [
        "short_lt_12_tokens",
        "medium_12_to_49_tokens",
        "long_50_plus_tokens",
    ]
    assert review_lengths["short_lt_12_tokens"]["reviewed_cases"] == 1
    assert review_lengths["medium_12_to_49_tokens"]["reviewed_cases"] == 2
    assert test_lengths["long_50_plus_tokens"]["reviewed_cases"] == 1
    assert all(
        row["false_merges"] == row["false_positive"]
        and row["missed_copies"] == row["false_negative"]
        for key in (
            "text_length_cohorts",
            "source_type_cohorts",
            "provider_cohorts",
        )
        for row in metrics["test"][key]
    )
    assert any(
        row["cohort_values"] == ["public_rss", "wire_service"]
        for row in metrics["test"]["provider_cohorts"]
    )
    assert any(
        row["cohort_values"] == ["broad_news", "original_reporting"]
        for row in metrics["test"]["source_type_cohorts"]
    )
    assert report["policy_conclusion"] == "insufficient_for_policy_change"
    assert report["descriptive_only"] is True
    assert report["auto_apply"] is False
    assert report["threshold_changes"] == 0
    assert report["route_changes"] == 0
    assert report["policy_changes"] == 0
    assert "minimum_independent_example_count_not_predeclared" in (
        report["policy_conclusion_reasons"]
    )
    assert "dependency_aware_uncertainty_not_estimated" in (
        report["policy_conclusion_reasons"]
    )
    assert oos.validate_descriptive_report(report) == []
    alias_drift = deepcopy(report)
    alias_drift["split_metrics"][2]["false_merges"] += 1
    assert "report_split_metrics_invalid" in oos.validate_descriptive_report(
        alias_drift
    )

    incomplete = oos.build_descriptive_report(
        corpus, oos.build_labeling_template_rows(corpus)
    )
    assert incomplete["status"] == "pending"
    assert incomplete["reviewed_case_count"] == 0
    assert incomplete["pending_case_count"] == corpus["case_count"]
    assert incomplete["reviewed_oos_coverage_complete"] is False
    assert "review_partition_not_fully_reviewed" in incomplete["oos_coverage_reasons"]
    assert "test_partition_not_fully_reviewed" in incomplete["oos_coverage_reasons"]
    assert incomplete["policy_conclusion"] == "insufficient_for_policy_change"
    assert oos.validate_descriptive_report(incomplete) == []


def test_invalid_reviews_fail_closed_without_descriptive_metrics():
    corpus = oos.build_frozen_corpus(
        [_case("invalid-review", prediction="independent")],
        split_salt=SPLIT_SALT,
    )
    reviews = _reviewed_rows(corpus, {"invalid-review": "independent"})
    reviews[0]["case_row_digest"] = "0" * 64

    report = oos.build_descriptive_report(corpus, reviews)

    assert report["status"] == "invalid_reviews"
    assert report["split_metrics"] == []
    assert report["reviewed_oos_coverage_complete"] is False
    assert "review_validation_failed" in report["policy_conclusion_reasons"]
    assert report["policy_conclusion"] == "insufficient_for_policy_change"
    assert oos.validate_descriptive_report(report) == []

    unsafe = deepcopy(report)
    unsafe["threshold_changes"] = 1
    assert "report_safety_contract_invalid" in oos.validate_descriptive_report(unsafe)


def test_cli_writes_only_explicit_immutable_outputs(tmp_path: Path, capsys):
    input_path = tmp_path / "cases.json"
    corpus_path = tmp_path / "frozen-corpus.json"
    template_path = tmp_path / "labels.jsonl"
    input_path.write_text(
        json.dumps({"cases": [_case("cli-case", prediction="duplicate")]}),
        encoding="utf-8",
    )

    args = [
        "export",
        "--input",
        str(input_path),
        "--corpus-out",
        str(corpus_path),
        "--template-out",
        str(template_path),
        "--split-salt",
        SPLIT_SALT,
    ]
    assert oos.main(args) == 0
    exported = json.loads(capsys.readouterr().out)
    assert exported["status"] == "exported"
    assert corpus_path.is_file()
    assert template_path.is_file()
    assert oos.main(args) == 0
    capsys.readouterr()

    before_validate = sorted(path.name for path in tmp_path.iterdir())
    assert oos.main(
        [
            "validate",
            "--corpus",
            str(corpus_path),
            "--reviews",
            str(template_path),
        ]
    ) == 2
    validation = json.loads(capsys.readouterr().out)
    assert validation["status"] == "valid"
    assert validation["pending_rows"] == 1
    assert sorted(path.name for path in tmp_path.iterdir()) == before_validate

    reviewed_path = tmp_path / "reviewed-labels.jsonl"
    corpus = oos.load_frozen_corpus(corpus_path)
    reviewed_path.write_text(
        oos.format_labeling_template_jsonl(
            _reviewed_rows(corpus, {"cli-case": "duplicate"})
        ),
        encoding="utf-8",
    )
    assert oos.main(
        [
            "validate",
            "--corpus",
            str(corpus_path),
            "--reviews",
            str(reviewed_path),
        ]
    ) == 0
    completed_validation = json.loads(capsys.readouterr().out)
    assert completed_validation["status"] == "valid"
    assert completed_validation["pending_rows"] == 0

    report_path = tmp_path / "descriptive-report.json"
    assert oos.main(
        [
            "report",
            "--corpus",
            str(corpus_path),
            "--reviews",
            str(template_path),
            "--output",
            str(report_path),
        ]
    ) == 2
    report_stdout = capsys.readouterr().out
    assert report_path.read_text(encoding="utf-8") == report_stdout
    assert json.loads(report_stdout)["policy_conclusion"] == (
        "insufficient_for_policy_change"
    )

    conflict_args = [*args[:-1], "another-declared-salt"]
    assert oos.main(conflict_args) == 2
    assert "immutable_output_conflict" in capsys.readouterr().err


def test_export_rejects_symlink_output_before_writing_peer(tmp_path: Path):
    input_path = tmp_path / "cases.json"
    input_path.write_text(json.dumps([_case("symlink-case")]), encoding="utf-8")
    existing = tmp_path / "existing.json"
    existing.write_text("do not replace", encoding="utf-8")
    corpus_link = tmp_path / "corpus.json"
    corpus_link.symlink_to(existing)
    template_path = tmp_path / "labels.jsonl"

    with pytest.raises(
        oos.SourceIndependenceOOSWorkflowError,
        match="explicit_output_path_unsafe",
    ):
        oos.export_workflow(
            input_path=input_path,
            corpus_output=corpus_link,
            template_output=template_path,
            split_salt=SPLIT_SALT,
        )

    assert existing.read_text(encoding="utf-8") == "do not replace"
    assert not template_path.exists()


def test_closed_oos_schemas_reject_boolean_versions() -> None:
    corpus = oos.build_frozen_corpus(
        [_case("strict-schema", prediction="duplicate")],
        split_salt=SPLIT_SALT,
    )

    top_level = deepcopy(corpus)
    top_level["schema_version"] = True
    _redigest(top_level)
    assert "corpus_schema_version_invalid" in oos.validate_frozen_corpus(top_level)

    split = deepcopy(corpus)
    split["split_declaration"]["schema_version"] = True
    split["split_declaration"]["declaration_digest"] = hashlib.sha256(
        json.dumps(
            {
                key: value
                for key, value in split["split_declaration"].items()
                if key != "declaration_digest"
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    _redigest(split)
    assert "corpus_split_schema_version_invalid" in oos.validate_frozen_corpus(split)

    case_row = deepcopy(corpus)
    case_row["rows"][0]["schema_version"] = True
    _redigest_case_row(case_row["rows"][0])
    _redigest(case_row)
    assert "corpus_case_schema_version_invalid" in oos.validate_frozen_corpus(
        case_row
    )

    reviews = oos.build_labeling_template_rows(corpus)
    reviews[0]["schema_version"] = True
    validation = oos.validate_review_rows(corpus, reviews)
    assert validation["status"] == "invalid"
    assert "review_schema_version_invalid" in validation["errors"][0]["error_codes"]


def test_persisted_split_metrics_reject_closed_shape_and_count_drift() -> None:
    review_duplicate = _family_id_for_split("review", "metric-review-duplicate")
    review_independent = _family_id_for_split(
        "review", "metric-review-independent"
    )
    test_duplicate = _family_id_for_split("test", "metric-test-duplicate")
    test_independent = _family_id_for_split("test", "metric-test-independent")
    corpus = oos.build_frozen_corpus(
        [
            _case(review_duplicate, prediction="duplicate"),
            _case(review_independent, prediction="independent"),
            _case(test_duplicate, prediction="duplicate"),
            _case(test_independent, prediction="independent"),
        ],
        split_salt=SPLIT_SALT,
    )
    report = oos.build_descriptive_report(
        corpus,
        _reviewed_rows(
            corpus,
            {
                review_duplicate: "duplicate",
                review_independent: "independent",
                test_duplicate: "duplicate",
                test_independent: "independent",
            },
        ),
    )
    assert report["status"] == "complete"
    assert oos.validate_descriptive_report(report) == []

    mutations = (
        ("boolean_schema", lambda value: value.update(schema_version=True), "report_schema_invalid"),
        (
            "unknown_split",
            lambda value: value["split_metrics"][0].update(split="holdout"),
            "report_split_metrics_invalid",
        ),
        (
            "unknown_category",
            lambda value: value["split_metrics"][1]["case_category_counts"].update(
                unknown_category=1
            ),
            "report_split_metrics_invalid",
        ),
        (
            "ratio_drift",
            lambda value: value["split_metrics"][1].update(reviewed_fraction=1.5),
            "report_split_metrics_invalid",
        ),
        (
            "count_drift",
            lambda value: value["split_metrics"][1].update(
                pending_cases=value["split_metrics"][1]["pending_cases"] + 1
            ),
            "report_split_metrics_invalid",
        ),
        (
            "count_type_drift",
            lambda value: value["split_metrics"][1].update(reviewed_cases="two"),
            "report_split_metrics_invalid",
        ),
    )
    for _label, mutate, expected in mutations:
        tampered = deepcopy(report)
        mutate(tampered)
        _redigest(tampered)
        assert expected in oos.validate_descriptive_report(tampered)
