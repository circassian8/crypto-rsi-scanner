"""CLI dispatch facade and extracted command-group routing."""

from __future__ import annotations

from typing import Sequence

from . import (
    commands_event_alpha,
    commands_export,
    commands_maintenance,
    commands_paper,
    commands_provider_readiness,
    commands_rsi,
)
from ._scanner_bindings import bind_scanner_globals
from .parser import CommandSnapshot, classify_command, command_group, dispatch_key_from_args


def dispatch_command_name(argv: Sequence[str]) -> str:
    return classify_command(argv).command_name


def apply_artifact_context(args) -> None:
    bind_scanner_globals(globals())
    if args.event_alpha_artifact_namespace:
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = args.event_alpha_artifact_namespace
        if not args.event_alpha_profile:
            _apply_event_alpha_artifact_context(None)



def dispatch_args(args) -> None:
    apply_artifact_context(args)
    if commands_export.handle(args):
        return
    if commands_rsi.handle_report(args):
        return
    if commands_paper.handle(args):
        return
    if commands_provider_readiness.handle(args):
        return
    if commands_event_alpha.handle(args):
        return
    if commands_maintenance.handle(args):
        return
    commands_rsi.handle_default_scan(args)


__all__ = (
    "CommandSnapshot",
    "apply_artifact_context",
    "classify_command",
    "command_group",
    "dispatch_args",
    "dispatch_command_name",
    "dispatch_key_from_args",
)
