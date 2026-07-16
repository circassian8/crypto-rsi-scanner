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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Frozen source-independence OOS labeling and descriptive evaluation; "
            "research-only, no providers, no automatic policy application."
        )
    )
    commands = parser.add_subparsers(dest="command", required=True)
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


__all__ = ("main",)
