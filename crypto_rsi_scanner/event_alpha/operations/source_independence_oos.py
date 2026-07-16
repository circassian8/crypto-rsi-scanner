"""Frozen out-of-sample labeling for source-independence research.

The workflow evaluates the existing source-independence v1 normalization,
minimum-length, and Jaccard rules against human-reviewed source pairs.  It is
deliberately descriptive: it cannot call providers, change thresholds or
routes, publish authority, or apply labels back into runtime artifacts.

Only paths explicitly supplied to an output argument may be written.  Frozen
outputs are immutable: rerunning with identical bytes is idempotent, while an
attempt to replace different bytes fails closed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

from ..radar import source_independence
from .source_independence_oos_partition import cross_split_leakage_errors
from .source_independence_oos_metrics import (
    ALGORITHM_PREDICTIONS,
    HUMAN_LABELS,
    OOS_SPLITS,
    build_split_metrics as _split_metrics,
    oos_coverage_reasons as _oos_coverage_reasons,
    validate_report_contract as _validate_report_contract,
)


CORPUS_SCHEMA_ID = "event_alpha.source_independence_oos_corpus"
CASE_SCHEMA_ID = "event_alpha.source_independence_oos_case"
LABEL_SCHEMA_ID = "event_alpha.source_independence_oos_label"
VALIDATION_SCHEMA_ID = "event_alpha.source_independence_oos_review_validation"
REPORT_SCHEMA_ID = "event_alpha.source_independence_oos_report"
SPLIT_SCHEMA_ID = "event_alpha.source_independence_oos_split"
SCHEMA_VERSION = 1
METHOD = "frozen_pairwise_source_independence_oos_v1"
DEFAULT_SPLIT_VERSION = "source_independence_oos_split_v3"
SPLITS = ("development", "review", "test")
SPLIT_BUCKET_MODULUS = 10_000
SPLIT_RANGES = {
    "development": (0, 5_999),
    "review": (6_000, 7_999),
    "test": (8_000, 9_999),
}
CASE_CATEGORIES = (
    "exact_syndicated_copy",
    "lightly_edited_cross_domain_copy",
    "independently_reported_same_event",
    "same_domain_original_update",
    "contradiction",
    "short_headline",
    "control",
)
REVIEW_STATUSES = ("pending", "reviewed")
POLICY_CONCLUSION = "insufficient_for_policy_change"
MAX_CASES = 4_096
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_CASE_ID_CHARS = 160
MAX_FAMILY_ID_CHARS = 160
MAX_SPLIT_TOKEN_CHARS = 256
MAX_REVIEWER_CHARS = 160
MAX_REVIEW_NOTES_CHARS = 4_096

_CASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_FAMILY_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_INPUT_CASE_KEYS = {
    "case_id",
    "case_category",
    "event_copy_family_id",
    "source_a",
    "source_b",
}
_SOURCE_KEYS = {
    "source_id",
    "provider",
    "source_class",
    "source_url",
    "published_at",
    "fetched_at",
    "title",
    "body",
}
_SPLIT_KEYS = {
    "schema_id",
    "schema_version",
    "split_version",
    "split_salt",
    "assignment_unit",
    "assignment_method",
    "bucket_modulus",
    "split_ranges",
    "declaration_digest",
}
_CASE_ROW_KEYS = {
    "schema_id",
    "schema_version",
    "case_id",
    "case_category",
    "event_copy_family_id",
    "source_a",
    "source_b",
    "source_a_digest",
    "source_b_digest",
    "source_a_content_digest",
    "source_b_content_digest",
    "source_a_origin",
    "source_b_origin",
    "source_a_assessment_status",
    "source_b_assessment_status",
    "source_a_token_count",
    "source_b_token_count",
    "case_input_digest",
    "algorithm_contract_digest",
    "algorithm_prediction",
    "algorithm_match_kind",
    "algorithm_similarity",
    "algorithm_reason_codes",
    "split",
    "split_bucket",
    "split_assignment_digest",
    "research_only",
    "row_digest",
}
_CORPUS_KEYS = {
    "schema_id",
    "schema_version",
    "method",
    "algorithm",
    "algorithm_digest",
    "split_declaration",
    "case_count",
    "split_counts",
    "case_category_counts",
    "distinct_source_providers",
    "distinct_source_origins",
    "rows",
    "research_only",
    "provider_calls",
    "writes_outside_explicit_outputs",
    "route_changes",
    "threshold_changes",
    "policy_changes",
    "auto_apply",
    "contract_digest",
}
_LABEL_BINDING_KEYS = {
    "schema_id",
    "schema_version",
    "corpus_digest",
    "case_id",
    "case_row_digest",
    "source_a",
    "source_b",
    "source_a_digest",
    "source_b_digest",
    "research_only",
}
_LABEL_REVIEW_KEYS = {
    "review_status",
    "human_label",
    "reviewed_by",
    "reviewed_at",
    "review_notes",
}
_LABEL_KEYS = _LABEL_BINDING_KEYS | _LABEL_REVIEW_KEYS
_VALIDATION_KEYS = {
    "schema_id",
    "schema_version",
    "status",
    "corpus_digest",
    "review_input_digest",
    "rows_supplied",
    "rows_expected",
    "matched_rows",
    "pending_rows",
    "reviewed_rows",
    "valid_reviewed_rows",
    "error_count",
    "errors",
    "reviewed_label_counts_by_split",
    "valid_review_digests",
    "research_only",
    "provider_calls",
    "writes_outside_explicit_outputs",
    "auto_apply",
    "contract_digest",
}


class SourceIndependenceOOSWorkflowError(ValueError):
    """Fail-closed input, binding, or immutable-output error."""


def build_split_declaration(*, split_salt: str, split_version: str) -> dict[str, Any]:
    """Build the declared deterministic development/review/test contract."""

    salt = _bounded_token(split_salt, "split_salt")
    version = _bounded_token(split_version, "split_version")
    value: dict[str, Any] = {
        "schema_id": SPLIT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "split_version": version,
        "split_salt": salt,
        "assignment_unit": "event_copy_family_id",
        "assignment_method": (
            "sha256_version_nul_salt_nul_event_copy_family_id_mod_10000"
        ),
        "bucket_modulus": SPLIT_BUCKET_MODULUS,
        "split_ranges": {
            name: [bounds[0], bounds[1]] for name, bounds in SPLIT_RANGES.items()
        },
    }
    value["declaration_digest"] = _digest(value)
    return value


def assign_split(
    event_copy_family_id: str, *, split_salt: str, split_version: str
) -> tuple[str, int, str]:
    """Assign one whole event/copy family without consulting labels."""

    identity = _family_id(event_copy_family_id)
    declaration = build_split_declaration(
        split_salt=split_salt, split_version=split_version
    )
    assignment_digest = hashlib.sha256(
        (
            declaration["split_version"]
            + "\0"
            + declaration["split_salt"]
            + "\0"
            + identity
        ).encode("utf-8")
    ).hexdigest()
    bucket = int(assignment_digest[:16], 16) % SPLIT_BUCKET_MODULUS
    split = next(
        name
        for name, (lower, upper) in SPLIT_RANGES.items()
        if lower <= bucket <= upper
    )
    return split, bucket, assignment_digest


def build_frozen_corpus(
    cases: Sequence[Mapping[str, Any]],
    *,
    split_salt: str,
    split_version: str = DEFAULT_SPLIT_VERSION,
) -> dict[str, Any]:
    """Build a deterministic, self-validating corpus from pairwise cases."""

    if isinstance(cases, (str, bytes, bytearray)) or not isinstance(cases, Sequence):
        raise SourceIndependenceOOSWorkflowError("corpus_cases_must_be_sequence")
    if not cases:
        raise SourceIndependenceOOSWorkflowError("corpus_cases_empty")
    if len(cases) > MAX_CASES:
        raise SourceIndependenceOOSWorkflowError("corpus_case_limit_exceeded")
    declaration = build_split_declaration(
        split_salt=split_salt, split_version=split_version
    )
    prepared = [_canonical_input_case(case) for case in cases]
    identities = [row["case_id"] for row in prepared]
    if len(set(identities)) != len(identities):
        raise SourceIndependenceOOSWorkflowError("corpus_case_id_duplicate")
    rows = [
        _build_case_row(
            row,
            split_salt=declaration["split_salt"],
            split_version=declaration["split_version"],
        )
        for row in sorted(prepared, key=lambda item: item["case_id"])
    ]
    leakage_errors = cross_split_leakage_errors(rows, allowed_splits=SPLITS)
    if leakage_errors:
        raise SourceIndependenceOOSWorkflowError(
            "corpus_cross_split_leakage:" + ",".join(leakage_errors)
        )
    providers = sorted(
        {
            str(source.get("provider") or "")
            for row in rows
            for source in (row["source_a"], row["source_b"])
            if str(source.get("provider") or "")
        }
    )
    origins = sorted(
        {
            str(value)
            for row in rows
            for value in (row["source_a_origin"], row["source_b_origin"])
            if value
        }
    )
    value: dict[str, Any] = {
        "schema_id": CORPUS_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "algorithm": dict(source_independence.ALGORITHM),
        "algorithm_digest": _digest(source_independence.ALGORITHM),
        "split_declaration": declaration,
        "case_count": len(rows),
        "split_counts": _closed_counts((row["split"] for row in rows), SPLITS),
        "case_category_counts": dict(
            sorted(Counter(row["case_category"] for row in rows).items())
        ),
        "distinct_source_providers": providers,
        "distinct_source_origins": origins,
        "rows": rows,
        "research_only": True,
        "provider_calls": 0,
        "writes_outside_explicit_outputs": 0,
        "route_changes": 0,
        "threshold_changes": 0,
        "policy_changes": 0,
        "auto_apply": False,
    }
    value["contract_digest"] = _digest(value)
    return value


def validate_frozen_corpus(value: Mapping[str, Any]) -> list[str]:
    """Recompute the complete corpus, including row and split assignments."""

    if not isinstance(value, Mapping):
        return ["corpus_not_mapping"]
    errors: list[str] = []
    if set(value) != _CORPUS_KEYS:
        errors.append("corpus_keys_invalid")
    if value.get("schema_id") != CORPUS_SCHEMA_ID:
        errors.append("corpus_schema_id_invalid")
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != SCHEMA_VERSION
    ):
        errors.append("corpus_schema_version_invalid")
    if value.get("method") != METHOD:
        errors.append("corpus_method_invalid")
    if value.get("research_only") is not True or value.get("auto_apply") is not False:
        errors.append("corpus_safety_contract_invalid")
    for key in (
        "provider_calls",
        "writes_outside_explicit_outputs",
        "route_changes",
        "threshold_changes",
        "policy_changes",
    ):
        if value.get(key) != 0:
            errors.append("corpus_safety_contract_invalid")
    rows = value.get("rows")
    declaration = value.get("split_declaration")
    if not isinstance(rows, list) or not isinstance(declaration, Mapping):
        errors.append("corpus_rows_or_split_invalid")
        return sorted(set(errors))
    if len(rows) > MAX_CASES:
        errors.append("corpus_case_limit_exceeded")
        return sorted(set(errors))
    if set(declaration) != _SPLIT_KEYS:
        errors.append("corpus_split_declaration_invalid")
    if (
        type(declaration.get("schema_version")) is not int
        or declaration.get("schema_version") != SCHEMA_VERSION
    ):
        errors.append("corpus_split_schema_version_invalid")
    cases: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _CASE_ROW_KEYS:
            errors.append("corpus_case_row_invalid")
            continue
        if (
            type(row.get("schema_version")) is not int
            or row.get("schema_version") != SCHEMA_VERSION
        ):
            errors.append("corpus_case_schema_version_invalid")
        row_digest = row.get("row_digest")
        if not _is_sha256(row_digest) or row_digest != _digest_without(row, "row_digest"):
            errors.append("corpus_case_row_digest_invalid")
        cases.append(
            {
                "case_id": row.get("case_id"),
                "case_category": row.get("case_category"),
                "event_copy_family_id": row.get("event_copy_family_id"),
                "source_a": row.get("source_a"),
                "source_b": row.get("source_b"),
            }
        )
    errors.extend(cross_split_leakage_errors(rows, allowed_splits=SPLITS))
    if errors:
        return sorted(set(errors))
    try:
        expected = build_frozen_corpus(
            cases,
            split_salt=str(declaration.get("split_salt") or ""),
            split_version=str(declaration.get("split_version") or ""),
        )
    except (SourceIndependenceOOSWorkflowError, TypeError, ValueError):
        return ["corpus_recomputation_failed"]
    if dict(value) != expected:
        errors.append("corpus_semantics_mismatch")
    return sorted(set(errors))


def build_labeling_template_rows(
    corpus: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Export blinded evidence rows; algorithm outputs and split are withheld."""

    errors = validate_frozen_corpus(corpus)
    if errors:
        raise SourceIndependenceOOSWorkflowError(
            "invalid_frozen_corpus:" + ",".join(errors)
        )
    corpus_digest = str(corpus["contract_digest"])
    return [
        {
            "schema_id": LABEL_SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "corpus_digest": corpus_digest,
            "case_id": row["case_id"],
            "case_row_digest": row["row_digest"],
            "source_a": dict(row["source_a"]),
            "source_b": dict(row["source_b"]),
            "source_a_digest": row["source_a_digest"],
            "source_b_digest": row["source_b_digest"],
            "research_only": True,
            "review_status": "pending",
            "human_label": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
        }
        for row in corpus["rows"]
    ]


def validate_review_rows(
    corpus: Mapping[str, Any], review_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Validate exact corpus bindings and human label provenance."""

    corpus_errors = validate_frozen_corpus(corpus)
    if corpus_errors:
        raise SourceIndependenceOOSWorkflowError(
            "invalid_frozen_corpus:" + ",".join(corpus_errors)
        )
    if isinstance(review_rows, (str, bytes, bytearray)) or not isinstance(
        review_rows, Sequence
    ):
        raise SourceIndependenceOOSWorkflowError("review_rows_must_be_sequence")
    expected_by_id = {
        row["case_id"]: row for row in build_labeling_template_rows(corpus)
    }
    corpus_case_by_id = {row["case_id"]: row for row in corpus["rows"]}
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    matched = 0
    pending = 0
    reviewed = 0
    valid_reviewed = 0
    valid_review_digests: list[str] = []
    label_counts: dict[str, Counter[str]] = {
        split: Counter() for split in SPLITS
    }
    materialized: list[Mapping[str, Any]] = []
    for index, supplied in enumerate(review_rows, start=1):
        if not isinstance(supplied, Mapping):
            errors.append(_review_error(index, "", "review_row_not_mapping"))
            continue
        row = dict(supplied)
        materialized.append(row)
        case_id = str(row.get("case_id") or "")
        row_errors: list[str] = []
        if set(row) != _LABEL_KEYS:
            row_errors.append("review_row_keys_invalid")
        if (
            type(row.get("schema_version")) is not int
            or row.get("schema_version") != SCHEMA_VERSION
        ):
            row_errors.append("review_schema_version_invalid")
        if case_id in seen:
            row_errors.append("review_case_id_duplicate")
        seen.add(case_id)
        expected = expected_by_id.get(case_id)
        if expected is None:
            row_errors.append("review_case_id_unknown")
        else:
            matched += 1
            for key in _LABEL_BINDING_KEYS:
                if row.get(key) != expected.get(key):
                    row_errors.append("review_case_binding_mismatch")
                    break
        status = row.get("review_status")
        if status not in REVIEW_STATUSES:
            row_errors.append("review_status_invalid")
        elif status == "pending":
            pending += 1
            if any(row.get(key) is not None for key in _LABEL_REVIEW_KEYS - {"review_status"}):
                row_errors.append("pending_review_fields_must_be_null")
        else:
            reviewed += 1
            row_errors.extend(_reviewed_field_errors(row))
        if row_errors:
            errors.append(_review_error(index, case_id, *row_errors))
            continue
        if status == "reviewed":
            valid_reviewed += 1
            split = corpus_case_by_id[case_id]["split"]
            label_counts[split][str(row["human_label"])] += 1
            valid_review_digests.append(_digest(row))
    missing_ids = sorted(set(expected_by_id) - seen)
    for case_id in missing_ids:
        errors.append(_review_error(0, case_id, "review_case_missing"))
    review_input_digest = _digest(
        sorted((dict(row) for row in materialized), key=lambda row: str(row.get("case_id") or ""))
    )
    result: dict[str, Any] = {
        "schema_id": VALIDATION_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "status": "valid" if not errors else "invalid",
        "corpus_digest": corpus["contract_digest"],
        "review_input_digest": review_input_digest,
        "rows_supplied": len(review_rows),
        "rows_expected": len(expected_by_id),
        "matched_rows": matched,
        "pending_rows": pending,
        "reviewed_rows": reviewed,
        "valid_reviewed_rows": valid_reviewed,
        "error_count": len(errors),
        "errors": errors,
        "reviewed_label_counts_by_split": {
            split: _closed_counts(label_counts[split].elements(), HUMAN_LABELS)
            for split in SPLITS
        },
        "valid_review_digests": sorted(valid_review_digests),
        "research_only": True,
        "provider_calls": 0,
        "writes_outside_explicit_outputs": 0,
        "auto_apply": False,
    }
    result["contract_digest"] = _digest(result)
    return result


def build_descriptive_report(
    corpus: Mapping[str, Any], review_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Compute split-specific descriptive metrics without policy eligibility."""

    validation = validate_review_rows(corpus, review_rows)
    reviews_by_id = {
        str(row.get("case_id") or ""): dict(row)
        for row in review_rows
        if isinstance(row, Mapping)
    }
    metrics = (
        [
            _split_metrics(
                split,
                [row for row in corpus["rows"] if row["split"] == split],
                reviews_by_id,
            )
            for split in SPLITS
        ]
        if validation["status"] == "valid"
        else []
    )
    coverage_reasons = _oos_coverage_reasons(metrics)
    coverage_complete = not coverage_reasons and validation["status"] == "valid"
    policy_reasons = [
        "descriptive_research_only_metrics",
        "minimum_independent_example_count_not_predeclared",
        "dependency_aware_uncertainty_not_estimated",
        "explicit_human_policy_approval_required",
        "automatic_policy_application_disabled",
    ]
    if validation["status"] != "valid":
        policy_reasons.append("review_validation_failed")
    if not coverage_complete:
        policy_reasons.append("reviewed_oos_coverage_incomplete")
    if validation["status"] != "valid":
        report_status = "invalid_reviews"
    elif int(validation["pending_rows"]) > 0:
        report_status = "pending"
    elif not coverage_complete:
        report_status = "incomplete"
    else:
        report_status = "complete"
    result: dict[str, Any] = {
        "schema_id": REPORT_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "method": METHOD,
        "status": report_status,
        "corpus_digest": corpus["contract_digest"],
        "review_input_digest": validation["review_input_digest"],
        "review_validation_digest": validation["contract_digest"],
        "algorithm": dict(corpus["algorithm"]),
        "algorithm_digest": corpus["algorithm_digest"],
        "split_declaration": dict(corpus["split_declaration"]),
        "case_count": corpus["case_count"],
        "reviewed_case_count": validation["valid_reviewed_rows"],
        "pending_case_count": validation["pending_rows"],
        "case_category_counts": dict(corpus["case_category_counts"]),
        "split_metrics": metrics,
        "oos_splits": list(OOS_SPLITS),
        "reviewed_oos_coverage_complete": coverage_complete,
        "oos_coverage_reasons": coverage_reasons,
        "policy_conclusion": POLICY_CONCLUSION,
        "policy_conclusion_reasons": policy_reasons,
        "descriptive_only": True,
        "research_only": True,
        "provider_calls": 0,
        "writes_outside_explicit_outputs": 0,
        "notifications_sent": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_rows_written": 0,
        "triggered_fade_created": 0,
        "route_changes": 0,
        "threshold_changes": 0,
        "policy_changes": 0,
        "authority_changes": 0,
        "auto_apply": False,
    }
    result["contract_digest"] = _digest(result)
    return result


def validate_descriptive_report(value: Mapping[str, Any]) -> list[str]:
    """Validate the closed shape and no-policy safety fields of one report."""

    return _validate_report_contract(
        value,
        schema_id=REPORT_SCHEMA_ID,
        schema_version=SCHEMA_VERSION,
        policy_conclusion=POLICY_CONCLUSION,
        splits=SPLITS,
        oos_splits=OOS_SPLITS,
        case_categories=CASE_CATEGORIES,
    )


def load_case_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read a bounded JSON or JSONL case input without any external I/O."""

    source = Path(path).expanduser()
    text = _read_bounded_text(source)
    if source.suffix.casefold() == ".jsonl":
        return _parse_jsonl(text, label="case")
    payload = _strict_json_loads(text)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping) and set(payload) == {"cases"}:
        rows = payload["cases"]
    else:
        raise SourceIndependenceOOSWorkflowError("case_input_json_shape_invalid")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise SourceIndependenceOOSWorkflowError("case_input_rows_invalid")
    return [dict(row) for row in rows]


def load_review_rows(path: str | Path) -> list[dict[str, Any]]:
    """Read the complete bounded JSONL review sidecar."""

    return _parse_jsonl(_read_bounded_text(Path(path).expanduser()), label="review")


def load_frozen_corpus(path: str | Path) -> dict[str, Any]:
    """Read and fully validate one frozen corpus JSON document."""

    payload = _strict_json_loads(_read_bounded_text(Path(path).expanduser()))
    if not isinstance(payload, Mapping):
        raise SourceIndependenceOOSWorkflowError("corpus_json_not_mapping")
    value = dict(payload)
    errors = validate_frozen_corpus(value)
    if errors:
        raise SourceIndependenceOOSWorkflowError(
            "invalid_frozen_corpus:" + ",".join(errors)
        )
    return value


def format_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def format_labeling_template_jsonl(rows: Iterable[Mapping[str, Any]]) -> str:
    lines = [
        _canonical_json(dict(row))
        for row in rows
    ]
    return ("\n".join(lines) + "\n") if lines else ""


def write_explicit_immutable_output(path: str | Path, text: str) -> Path:
    """Write only the named path; refuse symlinks and conflicting bytes."""

    target = Path(path).expanduser()
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_file():
            raise SourceIndependenceOOSWorkflowError("explicit_output_path_unsafe")
        if target.read_text(encoding="utf-8") != text:
            raise SourceIndependenceOOSWorkflowError("immutable_output_conflict")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise SourceIndependenceOOSWorkflowError("immutable_output_conflict") from exc
    try:
        data = text.encode("utf-8")
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return target


def export_workflow(
    *,
    input_path: str | Path,
    corpus_output: str | Path,
    template_output: str | Path,
    split_salt: str,
    split_version: str = DEFAULT_SPLIT_VERSION,
) -> dict[str, Any]:
    """Build and write exactly the two explicit immutable export outputs."""

    corpus_target = Path(corpus_output).expanduser()
    template_target = Path(template_output).expanduser()
    if corpus_target.absolute() == template_target.absolute():
        raise SourceIndependenceOOSWorkflowError("explicit_output_paths_must_differ")
    corpus = build_frozen_corpus(
        load_case_rows(input_path),
        split_salt=split_salt,
        split_version=split_version,
    )
    template_rows = build_labeling_template_rows(corpus)
    corpus_text = format_json(corpus)
    template_text = format_labeling_template_jsonl(template_rows)
    _preflight_immutable_output(corpus_target, corpus_text)
    _preflight_immutable_output(template_target, template_text)
    write_explicit_immutable_output(corpus_target, corpus_text)
    write_explicit_immutable_output(template_target, template_text)
    return {
        "status": "exported",
        "corpus_output": str(corpus_target),
        "template_output": str(template_target),
        "case_count": corpus["case_count"],
        "split_counts": corpus["split_counts"],
        "corpus_digest": corpus["contract_digest"],
        "research_only": True,
        "provider_calls": 0,
        "auto_apply": False,
    }


def _build_case_row(
    case: Mapping[str, Any], *, split_salt: str, split_version: str
) -> dict[str, Any]:
    source_a = dict(case["source_a"])
    source_b = dict(case["source_b"])
    contract = source_independence.assess_source_independence(
        [source_a, source_b]
    )
    if source_independence.validate_contract(contract):
        raise SourceIndependenceOOSWorkflowError(
            "source_independence_contract_invalid"
        )
    documents = {row["source_id"]: row for row in contract["documents"]}
    document_a = documents.get(source_a["source_id"])
    document_b = documents.get(source_b["source_id"])
    if document_a is None or document_b is None or len(documents) != 2:
        raise SourceIndependenceOOSWorkflowError("source_document_binding_failed")
    prediction, match_kind, similarity, reasons = _pair_prediction(
        document_a, document_b
    )
    split, bucket, assignment_digest = assign_split(
        str(case["event_copy_family_id"]),
        split_salt=split_salt,
        split_version=split_version,
    )
    case_input = {
        "case_id": case["case_id"],
        "case_category": case["case_category"],
        "event_copy_family_id": case["event_copy_family_id"],
        "source_a": source_a,
        "source_b": source_b,
    }
    row: dict[str, Any] = {
        "schema_id": CASE_SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "case_id": case["case_id"],
        "case_category": case["case_category"],
        "event_copy_family_id": case["event_copy_family_id"],
        "source_a": source_a,
        "source_b": source_b,
        "source_a_digest": _digest(source_a),
        "source_b_digest": _digest(source_b),
        "source_a_content_digest": document_a["content_digest"],
        "source_b_content_digest": document_b["content_digest"],
        "source_a_origin": document_a["canonical_origin"],
        "source_b_origin": document_b["canonical_origin"],
        "source_a_assessment_status": document_a["assessment_status"],
        "source_b_assessment_status": document_b["assessment_status"],
        "source_a_token_count": document_a["token_count"],
        "source_b_token_count": document_b["token_count"],
        "case_input_digest": _digest(case_input),
        "algorithm_contract_digest": contract["contract_digest"],
        "algorithm_prediction": prediction,
        "algorithm_match_kind": match_kind,
        "algorithm_similarity": similarity,
        "algorithm_reason_codes": reasons,
        "split": split,
        "split_bucket": bucket,
        "split_assignment_digest": assignment_digest,
        "research_only": True,
    }
    row["row_digest"] = _digest(row)
    return row


def _pair_prediction(
    document_a: Mapping[str, Any], document_b: Mapping[str, Any]
) -> tuple[str, str, float | None, list[str]]:
    if "rejected" in {
        document_a.get("assessment_status"),
        document_b.get("assessment_status"),
    } or not document_a.get("content_digest") or not document_b.get("content_digest"):
        return "unassessable", "rejected", None, ["source_input_rejected"]
    exact = document_a["content_digest"] == document_b["content_digest"]
    if exact:
        return "duplicate", "exact", 1.0, ["content_exact_duplicate"]
    both_assessable = all(
        document.get("content_similarity_status") == "assessable"
        for document in (document_a, document_b)
    )
    if not both_assessable:
        return (
            "unassessable",
            "too_short_or_missing_content",
            None,
            ["pair_content_similarity_unassessable"],
        )
    similarity = _normalized_text_jaccard(
        str(document_a["normalized_text"]),
        str(document_b["normalized_text"]),
    )
    same_cluster = document_a.get("cluster_id") == document_b.get("cluster_id")
    if same_cluster:
        return (
            "duplicate",
            "near_duplicate",
            similarity,
            ["content_near_duplicate"],
        )
    return "independent", "distinct", similarity, ["content_distinct"]


def _canonical_input_case(case: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(case, Mapping) or set(case) != _INPUT_CASE_KEYS:
        raise SourceIndependenceOOSWorkflowError("corpus_case_keys_invalid")
    case_id = _case_id(case.get("case_id"))
    family_id = _family_id(case.get("event_copy_family_id"))
    category = str(case.get("case_category") or "")
    if category not in CASE_CATEGORIES:
        raise SourceIndependenceOOSWorkflowError("corpus_case_category_invalid")
    source_a = _canonical_source(case.get("source_a"), label="source_a")
    source_b = _canonical_source(case.get("source_b"), label="source_b")
    if source_a["source_id"] == source_b["source_id"]:
        raise SourceIndependenceOOSWorkflowError("corpus_pair_source_ids_must_differ")
    return {
        "case_id": case_id,
        "case_category": category,
        "event_copy_family_id": family_id,
        "source_a": source_a,
        "source_b": source_b,
    }


def _canonical_source(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _SOURCE_KEYS:
        raise SourceIndependenceOOSWorkflowError(f"{label}_keys_invalid")
    source_id = value.get("source_id")
    if (
        not isinstance(source_id, str)
        or not source_id.strip()
        or source_id != source_id.strip()
        or len(source_id) > source_independence.MAX_SOURCE_ID_CHARS
    ):
        raise SourceIndependenceOOSWorkflowError(f"{label}_source_id_invalid")
    out: dict[str, Any] = {"source_id": source_id}
    for key in sorted(_SOURCE_KEYS - {"source_id"}):
        item = value.get(key)
        if item is not None and not isinstance(item, str):
            raise SourceIndependenceOOSWorkflowError(f"{label}_{key}_invalid")
        out[key] = item
    return {key: out[key] for key in sorted(_SOURCE_KEYS)}


def _reviewed_field_errors(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("human_label") not in HUMAN_LABELS:
        errors.append("human_label_invalid")
    reviewer = row.get("reviewed_by")
    if (
        not isinstance(reviewer, str)
        or not reviewer.strip()
        or reviewer != reviewer.strip()
        or len(reviewer) > MAX_REVIEWER_CHARS
    ):
        errors.append("reviewed_by_invalid")
    reviewed_at = row.get("reviewed_at")
    if _parse_aware_time(reviewed_at) is None:
        errors.append("reviewed_at_invalid")
    notes = row.get("review_notes")
    if (
        not isinstance(notes, str)
        or not notes.strip()
        or notes != notes.strip()
        or len(notes) > MAX_REVIEW_NOTES_CHARS
    ):
        errors.append("review_notes_invalid")
    return errors


def _review_error(index: int, case_id: str, *codes: str) -> dict[str, Any]:
    return {
        "row_index": index,
        "case_id": case_id,
        "error_codes": sorted(set(codes)),
    }


def _normalized_text_jaccard(left: str, right: str) -> float:
    size = source_independence.SHINGLE_SIZE
    left_words = left.split()
    right_words = right.split()
    left_shingles = {
        " ".join(left_words[index : index + size])
        for index in range(max(0, len(left_words) - size + 1))
    }
    right_shingles = {
        " ".join(right_words[index : index + size])
        for index in range(max(0, len(right_words) - size + 1))
    }
    union = left_shingles | right_shingles
    if not union:
        return 0.0
    return round(len(left_shingles & right_shingles) / len(union), 12)


def _case_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_CASE_ID_CHARS
        or not _CASE_ID_RE.fullmatch(value)
    ):
        raise SourceIndependenceOOSWorkflowError("corpus_case_id_invalid")
    return value


def _family_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > MAX_FAMILY_ID_CHARS
        or not _FAMILY_ID_RE.fullmatch(value)
    ):
        raise SourceIndependenceOOSWorkflowError("event_copy_family_id_invalid")
    return value


def _bounded_token(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
        or len(value) > MAX_SPLIT_TOKEN_CHARS
        or "\x00" in value
    ):
        raise SourceIndependenceOOSWorkflowError(f"{label}_invalid")
    return value


def _parse_aware_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _closed_counts(values: Iterable[str], allowed: Sequence[str]) -> dict[str, int]:
    counts = Counter(values)
    return {name: int(counts.get(name, 0)) for name in allowed}


def _strict_json_loads(text: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise SourceIndependenceOOSWorkflowError("json_duplicate_key")
            out[key] = value
        return out

    try:
        return json.loads(text, object_pairs_hook=unique_object)
    except SourceIndependenceOOSWorkflowError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise SourceIndependenceOOSWorkflowError("json_parse_error") from exc


def _parse_jsonl(text: str, *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = _strict_json_loads(line)
        if not isinstance(value, Mapping):
            raise SourceIndependenceOOSWorkflowError(
                f"{label}_jsonl_row_not_mapping:{line_number}"
            )
        rows.append(dict(value))
        if len(rows) > MAX_CASES:
            raise SourceIndependenceOOSWorkflowError(
                f"{label}_row_limit_exceeded"
            )
    return rows


def _read_bounded_text(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SourceIndependenceOOSWorkflowError("input_path_unreadable") from exc
    if size > MAX_INPUT_BYTES:
        raise SourceIndependenceOOSWorkflowError("input_file_size_limit_exceeded")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise SourceIndependenceOOSWorkflowError("input_path_unreadable") from exc


def _preflight_immutable_output(path: Path, text: str) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise SourceIndependenceOOSWorkflowError("explicit_output_path_unsafe")
        if path.read_text(encoding="utf-8") != text:
            raise SourceIndependenceOOSWorkflowError("immutable_output_conflict")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _digest_without(value: Mapping[str, Any], key: str) -> str:
    return _digest({name: child for name, child in value.items() if name != key})


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def main(argv: Sequence[str] | None = None) -> int:
    """Invoke the CLI without importing argparse during library use."""

    from .source_independence_oos_cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = (
    "ALGORITHM_PREDICTIONS",
    "CASE_CATEGORIES",
    "DEFAULT_SPLIT_VERSION",
    "HUMAN_LABELS",
    "OOS_SPLITS",
    "POLICY_CONCLUSION",
    "SPLITS",
    "SourceIndependenceOOSWorkflowError",
    "assign_split",
    "build_descriptive_report",
    "build_frozen_corpus",
    "build_labeling_template_rows",
    "build_split_declaration",
    "export_workflow",
    "format_json",
    "format_labeling_template_jsonl",
    "load_case_rows",
    "load_frozen_corpus",
    "load_review_rows",
    "main",
    "validate_descriptive_report",
    "validate_frozen_corpus",
    "validate_review_rows",
    "write_explicit_immutable_output",
)
