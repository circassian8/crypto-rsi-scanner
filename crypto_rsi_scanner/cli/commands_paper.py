"""Paper scoreboard CLI command handlers."""

from __future__ import annotations

from ._scanner_bindings import bind_scanner_globals

PAPER_COMMAND_GROUP = "paper"


def handle(args) -> bool:
    bind_scanner_globals(globals())
    if args.score:
        score(json_output=args.json, cohorts=args.cohorts)
        return True
    if args.refresh_paper:
        refresh_paper(verbose=args.verbose, json_output=args.json, cohorts=args.cohorts)
        return True
    return False
