"""RSI scanner CLI command handlers."""

from __future__ import annotations

from ._scanner_bindings import bind_scanner_globals

RSI_COMMAND_GROUP = "rsi"


def handle_report(args) -> bool:
    bind_scanner_globals(globals())
    if args.report:
        report()
        return True
    return False


def handle_default_scan(args) -> bool:
    bind_scanner_globals(globals())
    run(top_n=args.top_n, dry_run=args.dry_run, verbose=args.verbose)
    return True
