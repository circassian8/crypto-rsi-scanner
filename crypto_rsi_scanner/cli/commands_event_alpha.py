"""Event Alpha and event-research CLI command handlers."""

from __future__ import annotations

from .event_alpha_command_registry import EVENT_ALPHA_COMMANDS, dispatch_event_alpha_command

EVENT_ALPHA_COMMAND_GROUP = "event_alpha"


def handle(args) -> bool:
    return dispatch_event_alpha_command(args)


__all__ = ("EVENT_ALPHA_COMMANDS", "EVENT_ALPHA_COMMAND_GROUP", "handle")
