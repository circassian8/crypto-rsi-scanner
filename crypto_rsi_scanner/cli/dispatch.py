"""Dispatch facade for command-group extraction tests."""

from __future__ import annotations

from typing import Sequence

from .parser import CommandSnapshot, classify_command, command_group, dispatch_key_from_args


def dispatch_command_name(argv: Sequence[str]) -> str:
    return classify_command(argv).command_name


__all__ = (
    "CommandSnapshot",
    "classify_command",
    "command_group",
    "dispatch_command_name",
    "dispatch_key_from_args",
)
