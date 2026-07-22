"""Command-line entry point for frozen source-independence OOS research."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import sys

from .source_independence_oos import (
    DEFAULT_SPLIT_VERSION,
    SourceIndependenceOOSWorkflowError,
    build_descriptive_report,
    export_workflow,
    format_json,
    load_frozen_corpus,
    load_review_rows,
    validate_review_rows,
    write_explicit_immutable_output,
)
from .source_independence_oos_readiness import build_readiness_report


READINESS_JSON_COMMAND = (
    "make event-alpha-source-independence-oos-readiness "
    "SOURCE_INDEPENDENCE_OOS_READINESS_OUTPUT=json PYTHON=.venv/bin/python"
)


def format_readiness_summary(result: dict[str, object]) -> str:
    """Render the current human-evidence decision without exposing case rows."""

    configured = _mapping(result.get("configured"))
    case_input = _mapping(result.get("case_input"))
    corpus = _mapping(result.get("frozen_corpus"))
    template = _mapping(result.get("immutable_template"))
    reviews = _mapping(result.get("operator_reviews"))
    report = _mapping(result.get("descriptive_report_readiness"))
    blind = _mapping(result.get("blind_review_contract"))
    lines: list[tuple[str, object]] = [
        ("report", "event_alpha_source_independence_oos_readiness"),
        ("status", result.get("status")),
        ("readiness_digest", result.get("readiness_digest")),
        ("case_input_configured", configured.get("case_input")),
        ("case_input_status", case_input.get("status")),
        ("case_input_count", case_input.get("case_count")),
        ("split_salt_configured", configured.get("split_salt")),
        ("frozen_corpus_configured", configured.get("frozen_corpus")),
        ("frozen_corpus_status", corpus.get("status")),
        ("frozen_case_count", corpus.get("case_count")),
        ("immutable_template_configured", configured.get("immutable_template")),
        ("immutable_template_status", template.get("status")),
        ("template_pending_rows", template.get("pending_rows")),
        ("operator_reviews_configured", configured.get("operator_reviews")),
        ("operator_reviews_status", reviews.get("status")),
        ("reviewed_rows", reviews.get("valid_reviewed_rows")),
        ("pending_rows", reviews.get("pending_rows")),
        ("descriptive_report_status", report.get("status")),
        (
            "reviewed_oos_coverage_complete",
            report.get("reviewed_oos_coverage_complete"),
        ),
        ("policy_conclusion", report.get("policy_conclusion")),
        ("errors", result.get("errors")),
        ("next_action", result.get("next_action")),
        ("next_safe_command", result.get("next_safe_command")),
        ("label_from", blind.get("label_from")),
        ("do_not_label_from", blind.get("do_not_label_from")),
        ("expected_provider_activity", result.get("expected_provider_activity")),
        ("provider_calls", result.get("provider_calls")),
        ("writes", result.get("writes")),
        ("route_changes", result.get("route_changes")),
        ("threshold_changes", result.get("threshold_changes")),
        ("policy_changes", result.get("policy_changes")),
        (
            "automatic_policy_application",
            result.get("automatic_policy_application"),
        ),
        (
            "protocol_v2_evidence_eligible",
            result.get("protocol_v2_evidence_eligible"),
        ),
        ("research_only", result.get("research_only")),
        ("full_json_command", READINESS_JSON_COMMAND),
    ]
    return "\n".join(
        f"{key}={_summary_value(value)}"
        for key, value in lines
    )


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _summary_value(value: object) -> str:
    if value is None:
        return "none"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, tuple)):
        return ",".join(_summary_value(item) for item in value) or "none"
    return str(value).replace("\r", " ").replace("\n", " ").strip() or "none"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Frozen source-independence OOS labeling and descriptive evaluation; "
            "research-only, no providers, no automatic policy application."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
    readiness = commands.add_parser("readiness")
    readiness.add_argument("--input")
    readiness.add_argument("--corpus")
    readiness.add_argument("--template")
    readiness.add_argument("--reviews")
    readiness.add_argument("--split-salt-configured", action="store_true")
    readiness.add_argument("--output", choices=("json", "summary"), default="json")
    export = commands.add_parser("export")
    export.add_argument("--input", required=True)
    export.add_argument("--corpus-out", required=True)
    export.add_argument("--template-out", required=True)
    export.add_argument("--split-salt", required=True)
    export.add_argument("--split-version", default=DEFAULT_SPLIT_VERSION)
    validate = commands.add_parser("validate")
    validate.add_argument("--corpus", required=True)
    validate.add_argument("--reviews", required=True)
    validate.add_argument("--output")
    report = commands.add_parser("report")
    report.add_argument("--corpus", required=True)
    report.add_argument("--reviews", required=True)
    report.add_argument("--output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "readiness":
            result = build_readiness_report(
                input_path=args.input,
                corpus_path=args.corpus,
                template_path=args.template,
                reviews_path=args.reviews,
                split_salt_configured=args.split_salt_configured,
            )
            if args.output == "summary":
                sys.stdout.write(format_readiness_summary(result) + "\n")
            else:
                sys.stdout.write(format_json(result))
            return 2 if result["status"] == "invalid" else 0
        if args.command == "export":
            result = export_workflow(
                input_path=args.input,
                corpus_output=args.corpus_out,
                template_output=args.template_out,
                split_salt=args.split_salt,
                split_version=args.split_version,
            )
            sys.stdout.write(format_json(result))
            return 0
        corpus = load_frozen_corpus(args.corpus)
        reviews = load_review_rows(args.reviews)
        if args.command == "validate":
            result = validate_review_rows(corpus, reviews)
        else:
            result = build_descriptive_report(corpus, reviews)
        text = format_json(result)
        if args.output:
            write_explicit_immutable_output(args.output, text)
        sys.stdout.write(text)
        if args.command == "validate":
            return 0 if (
                result["status"] == "valid"
                and int(result.get("pending_rows") or 0) == 0
            ) else 2
        return 0 if result["status"] == "complete" else 2
    except (SourceIndependenceOOSWorkflowError, OSError, ValueError) as exc:
        message = str(exc).split(":", 1)[0] or type(exc).__name__
        sys.stderr.write(f"source_independence_oos_failed: {message}\n")
        return 2


__all__ = ("format_readiness_summary", "main")
