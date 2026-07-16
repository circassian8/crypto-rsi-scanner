"""Descriptive metrics for the frozen source-independence OOS workflow."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
import json
import math
import re
from typing import Any, Callable


HUMAN_LABELS = ("duplicate", "independent", "unassessable")
ALGORITHM_PREDICTIONS = HUMAN_LABELS
OOS_SPLITS = ("review", "test")
TEXT_LENGTH_COHORTS = (
    "short_lt_12_tokens",
    "medium_12_to_49_tokens",
    "long_50_plus_tokens",
)
_BEHAVIOR_KEYS = {
    "corpus_cases",
    "reviewed_cases",
    "pending_cases",
    "human_label_counts",
    "algorithm_prediction_counts",
    "confusion",
    "true_positive",
    "false_positive",
    "true_negative",
    "false_negative",
    "false_merges",
    "missed_copies",
    "algorithm_abstained_binary_labels",
    "precision_duplicate",
    "recall_duplicate",
}
COHORT_METRIC_KEYS = _BEHAVIOR_KEYS | {"cohort_dimension", "cohort_values"}
METRIC_KEYS = _BEHAVIOR_KEYS | {
    "split",
    "reviewed_fraction",
    "binary_label_fraction",
    "case_category_counts",
    "text_length_cohorts",
    "source_type_cohorts",
    "provider_cohorts",
}
REPORT_KEYS = {
    "schema_id",
    "schema_version",
    "method",
    "status",
    "corpus_digest",
    "review_input_digest",
    "review_validation_digest",
    "algorithm",
    "algorithm_digest",
    "split_declaration",
    "case_count",
    "reviewed_case_count",
    "pending_case_count",
    "case_category_counts",
    "split_metrics",
    "oos_splits",
    "reviewed_oos_coverage_complete",
    "oos_coverage_reasons",
    "policy_conclusion",
    "policy_conclusion_reasons",
    "descriptive_only",
    "research_only",
    "provider_calls",
    "writes_outside_explicit_outputs",
    "notifications_sent",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_rows_written",
    "triggered_fade_created",
    "route_changes",
    "threshold_changes",
    "policy_changes",
    "authority_changes",
    "auto_apply",
    "contract_digest",
}
_REPORT_STATUSES = {"complete", "pending", "incomplete", "invalid_reviews"}
_REPORT_ZERO_FIELDS = (
    "provider_calls",
    "writes_outside_explicit_outputs",
    "notifications_sent",
    "trades_created",
    "paper_trades_created",
    "normal_rsi_rows_written",
    "triggered_fade_created",
    "route_changes",
    "threshold_changes",
    "policy_changes",
    "authority_changes",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def build_split_metrics(
    split: str,
    case_rows: Sequence[Mapping[str, Any]],
    reviews_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one closed descriptive confusion and cohort row."""

    behavior = _behavior_metrics(case_rows, reviews_by_id)
    reviewed_rows = _reviewed_case_rows(case_rows, reviews_by_id)
    binary = sum(
        int(behavior["human_label_counts"].get(label, 0))
        for label in ("duplicate", "independent")
    )
    value = {
        "split": split,
        **behavior,
        "reviewed_fraction": _ratio(len(reviewed_rows), len(case_rows)),
        "binary_label_fraction": _ratio(binary, len(case_rows)),
        "case_category_counts": dict(
            sorted(Counter(row["case_category"] for row in reviewed_rows).items())
        ),
        "text_length_cohorts": _cohort_rows(
            dimension="text_length",
            case_rows=case_rows,
            reviews_by_id=reviews_by_id,
            classifier=_text_length_cohort,
            closed_values=((name,) for name in TEXT_LENGTH_COHORTS),
        ),
        "source_type_cohorts": _cohort_rows(
            dimension="source_type_pair",
            case_rows=case_rows,
            reviews_by_id=reviews_by_id,
            classifier=lambda row: _source_pair(row, "source_class"),
        ),
        "provider_cohorts": _cohort_rows(
            dimension="provider_pair",
            case_rows=case_rows,
            reviews_by_id=reviews_by_id,
            classifier=lambda row: _source_pair(row, "provider"),
        ),
    }
    if set(value) != METRIC_KEYS:
        raise AssertionError("source_independence_oos_metric_shape_drift")
    return value


def validate_split_metric(
    value: Mapping[str, Any],
    *,
    allowed_splits: Sequence[str],
    allowed_categories: Sequence[str],
) -> list[str]:
    """Validate closed split/cohort metric shapes and error aliases."""

    if not isinstance(value, Mapping) or set(value) != METRIC_KEYS:
        return ["split_metric_keys_invalid"]
    errors = _behavior_errors(value)
    if value.get("split") not in allowed_splits:
        errors.append("split_metric_split_invalid")
    errors.extend(_ratio_errors(value))
    errors.extend(
        _closed_category_count_errors(
            value.get("case_category_counts"),
            allowed_categories=allowed_categories,
            expected_total=value.get("reviewed_cases"),
        )
    )
    for key, dimension in (
        ("text_length_cohorts", "text_length"),
        ("source_type_cohorts", "source_type_pair"),
        ("provider_cohorts", "provider_pair"),
    ):
        rows = value.get(key)
        if not isinstance(rows, list):
            errors.append("split_metric_cohorts_invalid")
            continue
        seen: set[tuple[str, ...]] = set()
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != COHORT_METRIC_KEYS:
                errors.append("split_metric_cohort_shape_invalid")
                continue
            if row.get("cohort_dimension") != dimension:
                errors.append("split_metric_cohort_dimension_invalid")
            values = row.get("cohort_values")
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(item, str) or not item for item in values)
            ):
                errors.append("split_metric_cohort_values_invalid")
            else:
                identity = tuple(values)
                if identity in seen:
                    errors.append("split_metric_cohort_duplicate")
                seen.add(identity)
            errors.extend(_behavior_errors(row))
        errors.extend(
            _cohort_partition_errors(
                value,
                rows,
                label=key,
            )
        )
    text_rows = value.get("text_length_cohorts")
    if isinstance(text_rows, list):
        text_values = [tuple(row.get("cohort_values") or ()) for row in text_rows if isinstance(row, Mapping)]
        if text_values != [(name,) for name in TEXT_LENGTH_COHORTS]:
            errors.append("split_metric_text_length_cohorts_invalid")
    return sorted(set(errors))


def validate_report_contract(
    value: Mapping[str, Any],
    *,
    schema_id: str,
    schema_version: int,
    policy_conclusion: str,
    splits: Sequence[str],
    oos_splits: Sequence[str],
    case_categories: Sequence[str],
) -> list[str]:
    """Validate one persisted descriptive report without owning its policy."""

    if not isinstance(value, Mapping):
        return ["report_not_mapping"]
    errors: list[str] = []
    if set(value) != REPORT_KEYS:
        errors.append("report_keys_invalid")
    if (
        value.get("schema_id") != schema_id
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != schema_version
    ):
        errors.append("report_schema_invalid")
    if value.get("policy_conclusion") != policy_conclusion:
        errors.append("report_policy_conclusion_invalid")
    errors.extend(_report_state_errors(value))
    errors.extend(
        _report_metric_errors(
            value,
            splits=splits,
            oos_splits=oos_splits,
            case_categories=case_categories,
        )
    )
    if not _valid_contract_digest(value):
        errors.append("report_contract_digest_invalid")
    return sorted(set(errors))


def _report_state_errors(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    status = value.get("status")
    if status not in _REPORT_STATUSES:
        errors.append("report_status_invalid")
    pending_count = value.get("pending_case_count")
    coverage_complete = value.get("reviewed_oos_coverage_complete")
    if status == "complete" and (
        pending_count != 0 or coverage_complete is not True
    ):
        errors.append("report_status_incoherent")
    elif status == "pending" and (
        type(pending_count) is not int or pending_count <= 0
    ):
        errors.append("report_status_incoherent")
    elif status == "incomplete" and (
        pending_count != 0 or coverage_complete is not False
    ):
        errors.append("report_status_incoherent")
    if (
        value.get("descriptive_only") is not True
        or value.get("research_only") is not True
    ):
        errors.append("report_research_scope_invalid")
    if value.get("auto_apply") is not False:
        errors.append("report_auto_apply_invalid")
    if any(value.get(key) != 0 for key in _REPORT_ZERO_FIELDS):
        errors.append("report_safety_contract_invalid")
    return errors


def _report_metric_errors(
    value: Mapping[str, Any],
    *,
    splits: Sequence[str],
    oos_splits: Sequence[str],
    case_categories: Sequence[str],
) -> list[str]:
    errors: list[str] = []
    metrics = value.get("split_metrics")
    invalid_metrics = not isinstance(metrics, list) or any(
        not isinstance(row, Mapping)
        or set(row) != METRIC_KEYS
        or validate_split_metric(
            row,
            allowed_splits=splits,
            allowed_categories=case_categories,
        )
        for row in (metrics if isinstance(metrics, list) else ())
    )
    if not invalid_metrics and isinstance(metrics, list):
        metric_splits = [row.get("split") for row in metrics]
        invalid_metrics = (
            bool(metrics)
            if value.get("status") == "invalid_reviews"
            else metric_splits != list(splits)
        )
    if invalid_metrics:
        errors.append("report_split_metrics_invalid")
    if value.get("oos_splits") != list(oos_splits):
        errors.append("report_oos_splits_invalid")
    errors.extend(
        _report_category_errors(
            value,
            metrics=metrics,
            case_categories=case_categories,
        )
    )
    return errors


def _report_category_errors(
    value: Mapping[str, Any],
    *,
    metrics: object,
    case_categories: Sequence[str],
) -> list[str]:
    errors: list[str] = []
    case_count = value.get("case_count")
    category_counts = value.get("case_category_counts")
    if (
        type(case_count) is not int
        or case_count < 0
        or not isinstance(category_counts, Mapping)
        or not set(category_counts).issubset(set(case_categories))
        or any(
            type(count) is not int or count < 0
            for count in category_counts.values()
        )
        or sum(category_counts.values()) != case_count
    ):
        errors.append("report_case_category_counts_invalid")
    if (
        isinstance(metrics, list)
        and metrics
        and type(case_count) is int
        and all(type(row.get("corpus_cases")) is int for row in metrics)
        and sum(row["corpus_cases"] for row in metrics) != case_count
    ):
        errors.append("report_split_case_count_closure_invalid")
    return errors


def _valid_contract_digest(value: Mapping[str, Any]) -> bool:
    digest = value.get("contract_digest")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        return False
    payload = {key: child for key, child in value.items() if key != "contract_digest"}
    try:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        return False
    return hashlib.sha256(canonical).hexdigest() == digest


def oos_coverage_reasons(metrics: Sequence[Mapping[str, Any]]) -> list[str]:
    """Explain incomplete reviewed out-of-sample partition coverage."""

    by_split = {str(row.get("split")): row for row in metrics}
    reasons: list[str] = []
    for split in OOS_SPLITS:
        row = by_split.get(split)
        if row is None:
            reasons.append(f"{split}_metrics_missing")
            continue
        if int(row.get("corpus_cases") or 0) == 0:
            reasons.append(f"{split}_partition_empty")
            continue
        if row.get("reviewed_cases") != row.get("corpus_cases"):
            reasons.append(f"{split}_partition_not_fully_reviewed")
        label_counts = row.get("human_label_counts")
        if not isinstance(label_counts, Mapping):
            reasons.append(f"{split}_binary_label_coverage_missing")
        elif not label_counts.get("duplicate") or not label_counts.get("independent"):
            reasons.append(f"{split}_both_binary_labels_not_reviewed")
    return reasons


def _behavior_metrics(
    case_rows: Sequence[Mapping[str, Any]],
    reviews_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    pairs = [
        (str(review["human_label"]), str(case["algorithm_prediction"]))
        for case in case_rows
        if (review := reviews_by_id.get(str(case["case_id"])))
        and review.get("review_status") == "reviewed"
        and review.get("human_label") in HUMAN_LABELS
        and case.get("algorithm_prediction") in ALGORITHM_PREDICTIONS
    ]
    confusion = {
        human: {
            prediction: sum(
                1
                for actual, predicted in pairs
                if actual == human and predicted == prediction
            )
            for prediction in ALGORITHM_PREDICTIONS
        }
        for human in HUMAN_LABELS
    }
    tp = confusion["duplicate"]["duplicate"]
    fp = confusion["independent"]["duplicate"]
    tn = confusion["independent"]["independent"]
    fn = confusion["duplicate"]["independent"] + confusion["duplicate"]["unassessable"]
    return {
        "corpus_cases": len(case_rows),
        "reviewed_cases": len(pairs),
        "pending_cases": max(0, len(case_rows) - len(pairs)),
        "human_label_counts": _closed_counts((human for human, _ in pairs), HUMAN_LABELS),
        "algorithm_prediction_counts": _closed_counts(
            (prediction for _, prediction in pairs), ALGORITHM_PREDICTIONS
        ),
        "confusion": confusion,
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "false_merges": fp,
        "missed_copies": fn,
        "algorithm_abstained_binary_labels": sum(
            1
            for human, prediction in pairs
            if human != "unassessable" and prediction == "unassessable"
        ),
        "precision_duplicate": _ratio(tp, tp + fp),
        "recall_duplicate": _ratio(tp, tp + fn),
    }


def _reviewed_case_rows(
    case_rows: Sequence[Mapping[str, Any]],
    reviews_by_id: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return [
        case
        for case in case_rows
        if (review := reviews_by_id.get(str(case["case_id"])))
        and review.get("review_status") == "reviewed"
        and review.get("human_label") in HUMAN_LABELS
        and case.get("algorithm_prediction") in ALGORITHM_PREDICTIONS
    ]


def _cohort_rows(
    *,
    dimension: str,
    case_rows: Sequence[Mapping[str, Any]],
    reviews_by_id: Mapping[str, Mapping[str, Any]],
    classifier: Callable[[Mapping[str, Any]], tuple[str, ...]],
    closed_values: Iterable[tuple[str, ...]] = (),
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = {
        tuple(values): [] for values in closed_values
    }
    for case in case_rows:
        groups.setdefault(classifier(case), []).append(case)
    return [
        {
            "cohort_dimension": dimension,
            "cohort_values": list(values),
            **_behavior_metrics(groups[values], reviews_by_id),
        }
        for values in groups
    ]


def _text_length_cohort(case: Mapping[str, Any]) -> tuple[str, ...]:
    minimum = min(
        int(case.get("source_a_token_count") or 0),
        int(case.get("source_b_token_count") or 0),
    )
    if minimum < 12:
        return (TEXT_LENGTH_COHORTS[0],)
    if minimum < 50:
        return (TEXT_LENGTH_COHORTS[1],)
    return (TEXT_LENGTH_COHORTS[2],)


def _source_pair(case: Mapping[str, Any], key: str) -> tuple[str, ...]:
    values = []
    for source_key in ("source_a", "source_b"):
        source = case.get(source_key)
        raw = source.get(key) if isinstance(source, Mapping) else None
        values.append(str(raw) if isinstance(raw, str) and raw else "unknown")
    return tuple(sorted(values))


def _behavior_errors(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "corpus_cases",
        "reviewed_cases",
        "pending_cases",
        "true_positive",
        "false_positive",
        "true_negative",
        "false_negative",
        "false_merges",
        "missed_copies",
        "algorithm_abstained_binary_labels",
    ):
        if type(value.get(key)) is not int or int(value[key]) < 0:
            errors.append("split_metric_count_invalid")
    if value.get("false_merges") != value.get("false_positive"):
        errors.append("split_metric_false_merges_alias_invalid")
    if value.get("missed_copies") != value.get("false_negative"):
        errors.append("split_metric_missed_copies_alias_invalid")
    confusion = value.get("confusion")
    if not isinstance(confusion, Mapping) or set(confusion) != set(HUMAN_LABELS):
        errors.append("split_metric_confusion_invalid")
    elif any(
        not isinstance(row, Mapping)
        or set(row) != set(ALGORITHM_PREDICTIONS)
        or any(type(count) is not int or count < 0 for count in row.values())
        for row in confusion.values()
    ):
        errors.append("split_metric_confusion_invalid")
    for key in ("human_label_counts", "algorithm_prediction_counts"):
        counts = value.get(key)
        if (
            not isinstance(counts, Mapping)
            or set(counts) != set(HUMAN_LABELS)
            or any(type(count) is not int or count < 0 for count in counts.values())
        ):
            errors.append("split_metric_label_counts_invalid")
    for key in ("precision_duplicate", "recall_duplicate"):
        metric = value.get(key)
        if metric is not None and (
            not isinstance(metric, (int, float))
            or isinstance(metric, bool)
            or not math.isfinite(float(metric))
            or not 0.0 <= float(metric) <= 1.0
        ):
            errors.append("split_metric_ratio_invalid")
    if errors:
        return errors

    corpus_cases = int(value["corpus_cases"])
    reviewed_cases = int(value["reviewed_cases"])
    pending_cases = int(value["pending_cases"])
    if reviewed_cases + pending_cases != corpus_cases:
        errors.append("split_metric_review_count_closure_invalid")
    human_counts = value["human_label_counts"]
    prediction_counts = value["algorithm_prediction_counts"]
    if sum(human_counts.values()) != reviewed_cases:
        errors.append("split_metric_human_label_count_closure_invalid")
    if sum(prediction_counts.values()) != reviewed_cases:
        errors.append("split_metric_prediction_count_closure_invalid")
    confusion = value["confusion"]
    if sum(sum(row.values()) for row in confusion.values()) != reviewed_cases:
        errors.append("split_metric_confusion_count_closure_invalid")
    if any(
        sum(confusion[human].values()) != human_counts[human]
        for human in HUMAN_LABELS
    ):
        errors.append("split_metric_confusion_human_closure_invalid")
    if any(
        sum(confusion[human][prediction] for human in HUMAN_LABELS)
        != prediction_counts[prediction]
        for prediction in ALGORITHM_PREDICTIONS
    ):
        errors.append("split_metric_confusion_prediction_closure_invalid")

    expected_tp = confusion["duplicate"]["duplicate"]
    expected_fp = confusion["independent"]["duplicate"]
    expected_tn = confusion["independent"]["independent"]
    expected_fn = (
        confusion["duplicate"]["independent"]
        + confusion["duplicate"]["unassessable"]
    )
    if value["true_positive"] != expected_tp:
        errors.append("split_metric_true_positive_invalid")
    if value["false_positive"] != expected_fp:
        errors.append("split_metric_false_positive_invalid")
    if value["true_negative"] != expected_tn:
        errors.append("split_metric_true_negative_invalid")
    if value["false_negative"] != expected_fn:
        errors.append("split_metric_false_negative_invalid")
    expected_abstained = (
        confusion["duplicate"]["unassessable"]
        + confusion["independent"]["unassessable"]
    )
    if value["algorithm_abstained_binary_labels"] != expected_abstained:
        errors.append("split_metric_abstained_count_invalid")
    if value["precision_duplicate"] != _ratio(expected_tp, expected_tp + expected_fp):
        errors.append("split_metric_precision_invalid")
    if value["recall_duplicate"] != _ratio(expected_tp, expected_tp + expected_fn):
        errors.append("split_metric_recall_invalid")
    return errors


def _ratio_errors(value: Mapping[str, Any]) -> list[str]:
    corpus_cases = value.get("corpus_cases")
    reviewed_cases = value.get("reviewed_cases")
    human_counts = value.get("human_label_counts")
    if (
        type(corpus_cases) is not int
        or corpus_cases < 0
        or type(reviewed_cases) is not int
        or reviewed_cases < 0
        or not isinstance(human_counts, Mapping)
        or any(type(count) is not int or count < 0 for count in human_counts.values())
    ):
        return ["split_metric_fraction_basis_invalid"]
    expected_reviewed = _ratio(reviewed_cases, corpus_cases)
    binary = sum(int(human_counts.get(label) or 0) for label in ("duplicate", "independent"))
    expected_binary = _ratio(binary, corpus_cases)
    errors: list[str] = []
    if value.get("reviewed_fraction") != expected_reviewed:
        errors.append("split_metric_reviewed_fraction_invalid")
    if value.get("binary_label_fraction") != expected_binary:
        errors.append("split_metric_binary_label_fraction_invalid")
    return errors


def _closed_category_count_errors(
    value: object,
    *,
    allowed_categories: Sequence[str],
    expected_total: object,
) -> list[str]:
    if (
        not isinstance(value, Mapping)
        or not set(value).issubset(set(allowed_categories))
        or any(type(count) is not int or count < 0 for count in value.values())
    ):
        return ["split_metric_case_category_counts_invalid"]
    if type(expected_total) is not int or sum(value.values()) != expected_total:
        return ["split_metric_case_category_count_closure_invalid"]
    return []


def _cohort_partition_errors(
    parent: Mapping[str, Any],
    rows: object,
    *,
    label: str,
) -> list[str]:
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        return []
    errors: list[str] = []
    for field in ("corpus_cases", "reviewed_cases", "pending_cases"):
        expected = parent.get(field)
        observed = [row.get(field) for row in rows]
        if (
            type(expected) is not int
            or any(type(count) is not int or count < 0 for count in observed)
            or sum(observed) != expected
        ):
            errors.append(f"split_metric_{label}_count_closure_invalid")
            break
    for count_key in ("human_label_counts", "algorithm_prediction_counts"):
        parent_counts = parent.get(count_key)
        if not isinstance(parent_counts, Mapping):
            continue
        child_counts = [row.get(count_key) for row in rows]
        if any(
            not isinstance(counts, Mapping)
            or any(type(count) is not int or count < 0 for count in counts.values())
            for counts in child_counts
        ):
            errors.append(f"split_metric_{label}_{count_key}_closure_invalid")
            continue
        if any(
            sum(
                counts.get(name, 0)
                for counts in child_counts
            )
            != parent_counts.get(name)
            for name in HUMAN_LABELS
        ):
            errors.append(f"split_metric_{label}_{count_key}_closure_invalid")
    return errors


def _closed_counts(values: Iterable[str], allowed: Sequence[str]) -> dict[str, int]:
    counts = Counter(values)
    return {name: int(counts.get(name, 0)) for name in allowed}


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    value = numerator / denominator
    if not math.isfinite(value):
        return None
    return round(value, 12)


__all__ = (
    "ALGORITHM_PREDICTIONS",
    "COHORT_METRIC_KEYS",
    "HUMAN_LABELS",
    "METRIC_KEYS",
    "OOS_SPLITS",
    "REPORT_KEYS",
    "TEXT_LENGTH_COHORTS",
    "build_split_metrics",
    "oos_coverage_reasons",
    "validate_report_contract",
    "validate_split_metric",
)
