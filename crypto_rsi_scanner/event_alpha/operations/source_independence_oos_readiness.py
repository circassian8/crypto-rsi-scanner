"""Read-only readiness for frozen source-independence OOS human labeling."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from . import source_independence_oos as oos


SCHEMA_ID = "event_alpha.source_independence_oos_readiness"
SCHEMA_VERSION = 1
_CASE_INPUT_KEYS = (
    "case_id",
    "case_category",
    "event_copy_family_id",
    "source_a",
    "source_b",
)
_SOURCE_KEYS = (
    "source_id",
    "provider",
    "source_class",
    "source_url",
    "published_at",
    "fetched_at",
    "title",
    "body",
)


def build_readiness_report(
    *,
    input_path: str | Path | None = None,
    corpus_path: str | Path | None = None,
    template_path: str | Path | None = None,
    reviews_path: str | Path | None = None,
    split_salt_configured: bool = False,
) -> dict[str, Any]:
    """Inspect each frozen-workflow stage without writing or revealing labels."""

    state = _inspect_stages(
        input_path=input_path,
        corpus_path=corpus_path,
        template_path=template_path,
        reviews_path=reviews_path,
    )
    status = _readiness_status(
        errors=state["errors"],
        input_configured=state["input_configured"],
        case_input=state["case_input"],
        corpus=state["corpus"],
        template_configured=state["template_configured"],
        template_summary=state["template_summary"],
        reviews_configured=state["reviews_configured"],
        review_validation=state["review_validation"],
        report_summary=state["report_summary"],
        split_salt_configured=split_salt_configured,
    )
    next_action, next_safe_command = _next_action(status)
    result: dict[str, Any] = {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "configured": {
            "case_input": state["input_configured"],
            "frozen_corpus": state["corpus_configured"],
            "immutable_template": state["template_configured"],
            "operator_reviews": state["reviews_configured"],
            "split_salt": split_salt_configured,
        },
        "case_input": state["case_input"],
        "frozen_corpus": state["corpus_summary"],
        "immutable_template": state["template_summary"],
        "operator_reviews": state["reviews_summary"],
        "descriptive_report_readiness": state["report_summary"],
        "errors": sorted(set(state["errors"])),
        "next_action": next_action,
        "next_safe_command": next_safe_command,
        "case_input_contract": {
            "container": "JSON list, {cases:[...]}, or JSONL",
            "required_case_fields": list(_CASE_INPUT_KEYS),
            "required_source_fields": list(_SOURCE_KEYS),
            "case_categories": list(oos.CASE_CATEGORIES),
            "event_copy_family_id_is_human_curated": True,
            "case_category_is_human_curated": True,
            "fixtures_are_genuine_evidence": False,
        },
        "blind_review_contract": {
            "label_from": "immutable_template_copy_only",
            "do_not_label_from": "frozen_corpus",
            "algorithm_predictions_exposed": False,
            "per_case_split_assignments_exposed": False,
            "human_labels_created": 0,
        },
        "expected_provider_activity": "none",
        "provider_calls": 0,
        "writes": 0,
        "route_changes": 0,
        "threshold_changes": 0,
        "policy_changes": 0,
        "automatic_policy_application": False,
        "protocol_v2_evidence_eligible": False,
        "research_only": True,
        "safety": {
            "notifications_sent": 0,
            "trades_created": 0,
            "paper_trades_created": 0,
            "normal_rsi_rows_written": 0,
            "triggered_fade_created": 0,
        },
    }
    result["readiness_digest"] = _digest(result)
    return result


def _inspect_stages(
    *,
    input_path: str | Path | None,
    corpus_path: str | Path | None,
    template_path: str | Path | None,
    reviews_path: str | Path | None,
) -> dict[str, Any]:
    errors: list[str] = []
    input_configured = _configured(input_path)
    corpus_configured = _configured(corpus_path)
    template_configured = _configured(template_path)
    reviews_configured = _configured(reviews_path)
    case_input = _inspect_case_input(input_path, errors=errors)
    corpus, corpus_summary = _inspect_corpus(corpus_path, errors=errors)
    template_summary = _not_configured()
    if template_configured:
        if corpus is None:
            template_summary = _corpus_required(errors, "template")
        else:
            template_summary = _review_file_summary(
                corpus,
                _path(template_path),
                require_all_pending=True,
                error_prefix="template",
                errors=errors,
            )
    if _same_configured_path(template_path, reviews_path):
        errors.append("reviews_must_be_separate_template_copy")
        review_rows = None
        review_validation = None
        reviews_summary = {
            "status": "invalid",
            "error": "reviews_must_be_separate_template_copy",
        }
    else:
        review_rows, review_validation, reviews_summary = _inspect_reviews(
            corpus,
            reviews_path,
            errors=errors,
        )
    report_summary = _inspect_report(corpus, review_rows, review_validation)
    return {
        "errors": errors,
        "input_configured": input_configured,
        "corpus_configured": corpus_configured,
        "template_configured": template_configured,
        "reviews_configured": reviews_configured,
        "case_input": case_input,
        "corpus": corpus,
        "corpus_summary": corpus_summary,
        "template_summary": template_summary,
        "review_validation": review_validation,
        "reviews_summary": reviews_summary,
        "report_summary": report_summary,
    }


def _inspect_case_input(
    path: str | Path | None, *, errors: list[str]
) -> dict[str, Any]:
    if not _configured(path):
        return _not_configured()
    try:
        return oos.summarize_case_input(oos.load_case_rows(_path(path)))
    except (oos.SourceIndependenceOOSWorkflowError, OSError, ValueError) as exc:
        errors.append("case_input_invalid")
        return {"status": "invalid", "error": _error_code(exc)}


def _inspect_corpus(
    path: str | Path | None, *, errors: list[str]
) -> tuple[Mapping[str, Any] | None, dict[str, Any]]:
    if not _configured(path):
        return None, _not_configured()
    try:
        corpus = oos.load_frozen_corpus(_path(path))
    except (oos.SourceIndependenceOOSWorkflowError, OSError, ValueError) as exc:
        errors.append("frozen_corpus_invalid")
        return None, {"status": "invalid", "error": _error_code(exc)}
    return corpus, {
        "status": "valid",
        "case_count": corpus["case_count"],
        "split_counts": dict(corpus["split_counts"]),
        "case_category_counts": dict(corpus["case_category_counts"]),
        "distinct_source_providers": list(corpus["distinct_source_providers"]),
        "distinct_source_origins": list(corpus["distinct_source_origins"]),
        "corpus_digest": corpus["contract_digest"],
        "provider_calls": 0,
        "research_only": True,
    }


def _inspect_reviews(
    corpus: Mapping[str, Any] | None,
    path: str | Path | None,
    *,
    errors: list[str],
) -> tuple[
    list[dict[str, Any]] | None,
    Mapping[str, Any] | None,
    dict[str, Any],
]:
    if not _configured(path):
        return None, None, _not_configured()
    if corpus is None:
        return None, None, _corpus_required(errors, "reviews")
    try:
        rows = oos.load_review_rows(_path(path))
        validation = oos.validate_review_rows(corpus, rows)
    except (oos.SourceIndependenceOOSWorkflowError, OSError, ValueError) as exc:
        errors.append("reviews_invalid")
        return None, None, {"status": "invalid", "error": _error_code(exc)}
    if validation["status"] != "valid":
        errors.append("reviews_invalid")
    return rows, validation, _validation_summary(validation)


def _inspect_report(
    corpus: Mapping[str, Any] | None,
    rows: list[dict[str, Any]] | None,
    validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if corpus is None or rows is None or validation is None:
        return _not_configured()
    if validation["status"] != "valid":
        return _not_configured()
    report = oos.build_descriptive_report(corpus, rows)
    return {
        "status": report["status"],
        "reviewed_case_count": report["reviewed_case_count"],
        "pending_case_count": report["pending_case_count"],
        "reviewed_oos_coverage_complete": report[
            "reviewed_oos_coverage_complete"
        ],
        "oos_coverage_reasons": list(report["oos_coverage_reasons"]),
        "policy_conclusion": report["policy_conclusion"],
        "descriptive_only": True,
    }


def _corpus_required(errors: list[str], prefix: str) -> dict[str, str]:
    errors.append(f"{prefix}_without_valid_corpus")
    return {"status": "not_checked", "reason": "valid_frozen_corpus_required"}


def _review_file_summary(
    corpus: Mapping[str, Any],
    path: Path,
    *,
    require_all_pending: bool,
    error_prefix: str,
    errors: list[str],
) -> dict[str, Any]:
    try:
        rows = oos.load_review_rows(path)
        validation = oos.validate_review_rows(corpus, rows)
    except (oos.SourceIndependenceOOSWorkflowError, OSError, ValueError) as exc:
        errors.append(f"{error_prefix}_invalid")
        return {"status": "invalid", "error": _error_code(exc)}
    summary = _validation_summary(validation)
    if validation["status"] != "valid":
        errors.append(f"{error_prefix}_invalid")
    elif require_all_pending and (
        validation["reviewed_rows"] != 0
        or validation["pending_rows"] != validation["rows_expected"]
    ):
        summary["status"] = "invalid"
        summary["error"] = "immutable_template_must_be_all_pending"
        errors.append(f"{error_prefix}_invalid")
    return summary


def _validation_summary(validation: Mapping[str, Any]) -> dict[str, Any]:
    error_codes = sorted(
        {
            str(code)
            for row in validation.get("errors", [])
            if isinstance(row, Mapping)
            for code in row.get("error_codes", [])
        }
    )
    return {
        "status": validation["status"],
        "rows_expected": validation["rows_expected"],
        "rows_supplied": validation["rows_supplied"],
        "matched_rows": validation["matched_rows"],
        "pending_rows": validation["pending_rows"],
        "reviewed_rows": validation["reviewed_rows"],
        "valid_reviewed_rows": validation["valid_reviewed_rows"],
        "error_count": validation["error_count"],
        "error_codes": error_codes,
        "review_input_digest": validation["review_input_digest"],
    }


def _readiness_status(
    *,
    errors: list[str],
    input_configured: bool,
    case_input: Mapping[str, Any],
    corpus: Mapping[str, Any] | None,
    template_configured: bool,
    template_summary: Mapping[str, Any],
    reviews_configured: bool,
    review_validation: Mapping[str, Any] | None,
    report_summary: Mapping[str, Any],
    split_salt_configured: bool,
) -> str:
    if errors:
        return "invalid"
    if corpus is None:
        if not input_configured:
            return "case_input_required"
        if case_input.get("status") != "valid":
            return "invalid"
        if not split_salt_configured:
            return "split_salt_required"
        return "ready_to_freeze"
    if not template_configured or template_summary.get("status") != "valid":
        return "immutable_template_required"
    if not reviews_configured:
        return "ready_for_human_labels"
    if review_validation is None or review_validation.get("status") != "valid":
        return "invalid"
    if int(review_validation.get("pending_rows") or 0) > 0:
        return "human_labels_pending"
    if report_summary.get("status") == "complete":
        return "descriptive_report_ready"
    return "oos_coverage_incomplete"


def _next_action(status: str) -> tuple[str, str]:
    if status == "case_input_required":
        return (
            "prepare_source_diverse_case_input",
            "Prepare genuine JSON/JSONL pairs using case_input_contract; do not use fixtures.",
        )
    if status == "split_salt_required":
        return (
            "choose_stable_split_salt",
            "Choose one stable non-secret split salt before freezing; do not inspect assignments.",
        )
    if status == "ready_to_freeze":
        return (
            "freeze_corpus_and_blind_template",
            "make event-alpha-source-independence-oos-export SOURCE_INDEPENDENCE_OOS_INPUT=/absolute/path/cases.json SOURCE_INDEPENDENCE_OOS_CORPUS=/absolute/path/frozen-corpus.json SOURCE_INDEPENDENCE_OOS_TEMPLATE=/absolute/path/blind-template.jsonl SOURCE_INDEPENDENCE_OOS_SPLIT_SALT=<stable-salt> PYTHON=.venv/bin/python",
        )
    if status == "immutable_template_required":
        return (
            "restore_exact_immutable_template",
            "Re-run the identical export inputs to restore the missing immutable blind template.",
        )
    if status == "ready_for_human_labels":
        return (
            "copy_template_and_begin_blind_review",
            "Copy the immutable template to a separate operator-owned review JSONL; label only that copy.",
        )
    if status == "human_labels_pending":
        return (
            "complete_pending_human_labels",
            "Complete every pending row in the operator review copy, then rerun readiness.",
        )
    if status == "descriptive_report_ready":
        return (
            "render_descriptive_report",
            "make event-alpha-source-independence-oos-report SOURCE_INDEPENDENCE_OOS_CORPUS=/absolute/path/frozen-corpus.json SOURCE_INDEPENDENCE_OOS_REVIEWS=/absolute/path/reviews.jsonl PYTHON=.venv/bin/python",
        )
    if status == "oos_coverage_incomplete":
        return (
            "plan_new_independent_corpus_version",
            "Add genuinely independent cases through a new frozen corpus version; do not alter the current labels or threshold.",
        )
    return (
        "repair_invalid_input",
        "Inspect the bounded error codes, repair the explicit local files, and rerun readiness.",
    )


def _configured(value: str | Path | None) -> bool:
    return bool(str(value or "").strip())


def _same_configured_path(
    left: str | Path | None, right: str | Path | None
) -> bool:
    return bool(
        _configured(left)
        and _configured(right)
        and _path(left).absolute() == _path(right).absolute()
    )


def _path(value: str | Path | None) -> Path:
    return Path(str(value)).expanduser()


def _not_configured() -> dict[str, str]:
    return {"status": "not_configured"}


def _error_code(exc: BaseException) -> str:
    return (str(exc).split(":", 1)[0] or type(exc).__name__)[:160]


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


__all__ = ("build_readiness_report",)
