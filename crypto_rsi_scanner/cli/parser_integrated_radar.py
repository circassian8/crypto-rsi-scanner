"""Integrated Radar and exact observed-outcome CLI arguments."""

from __future__ import annotations

import argparse


OBSERVED_OUTCOME_COMMAND_DEST = "event_alpha_observed_outcome_build"
OBSERVED_OUTCOME_OPTION_DESTS = (
    "event_alpha_observed_candidates",
    "event_alpha_observed_cores",
    "event_alpha_observed_closes",
    "event_alpha_observed_candidate_id",
    "event_alpha_observed_core_id",
    "event_alpha_observed_evaluated_at",
)
OBSERVED_OUTCOME_ALLOWED_DESTS = frozenset(
    {
        OBSERVED_OUTCOME_COMMAND_DEST,
        *OBSERVED_OUTCOME_OPTION_DESTS,
        "confirm",
        "event_alpha_artifact_namespace",
        "event_alpha_profile",
        "json",
        "out",
        "verbose",
    }
)


def observed_outcome_args_supplied(args: argparse.Namespace) -> bool:
    """Return whether an exact observed-outcome command or option was supplied."""

    if bool(getattr(args, OBSERVED_OUTCOME_COMMAND_DEST, False)):
        return True
    return any(
        getattr(args, destination, None) not in (None, "")
        for destination in OBSERVED_OUTCOME_OPTION_DESTS
    )


def observed_outcome_has_command_conflict(args: argparse.Namespace) -> bool:
    """Fail closed when another CLI command is combined with this operator."""

    from .parser import build_parser

    defaults = vars(build_parser().parse_args([]))
    return any(
        destination not in OBSERVED_OUTCOME_ALLOWED_DESTS
        and value != defaults.get(destination)
        for destination, value in vars(args).items()
    )


def add_integrated_radar_args(parser: argparse.ArgumentParser) -> None:
    """Add explicit offline observed-outcome operator arguments."""

    parser.add_argument(
        "--event-alpha-observed-outcome-build",
        action="store_true",
        help=(
            "Preview one exact observed-market Event Alpha outcome from explicit local "
            "authority files; writing requires both --out and --confirm."
        ),
    )
    parser.add_argument(
        "--event-alpha-observed-candidates",
        metavar="CANDIDATES_JSONL",
        help="Integrated-candidate authority JSONL for the observed-outcome preview.",
    )
    parser.add_argument(
        "--event-alpha-observed-cores",
        metavar="CORES_JSONL",
        help="Core Opportunity authority JSONL for the observed-outcome preview.",
    )
    parser.add_argument(
        "--event-alpha-observed-closes",
        metavar="CLOSES_JSON",
        help="Observed close-price fixture JSON for the observed-outcome preview.",
    )
    parser.add_argument(
        "--event-alpha-observed-candidate-id",
        metavar="CANDIDATE_ID",
        help="Exact candidate identity to select from the candidate authority file.",
    )
    parser.add_argument(
        "--event-alpha-observed-core-id",
        metavar="CORE_ID",
        help="Exact Core Opportunity identity required by the selected candidate.",
    )
    parser.add_argument(
        "--event-alpha-observed-evaluated-at",
        metavar="UTC_ISO8601",
        help="Explicit aware UTC evaluation clock for maturity and price selection.",
    )


__all__ = (
    "OBSERVED_OUTCOME_ALLOWED_DESTS",
    "OBSERVED_OUTCOME_COMMAND_DEST",
    "OBSERVED_OUTCOME_OPTION_DESTS",
    "add_integrated_radar_args",
    "observed_outcome_args_supplied",
    "observed_outcome_has_command_conflict",
)
