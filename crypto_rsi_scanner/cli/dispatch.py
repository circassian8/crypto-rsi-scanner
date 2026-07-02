"""Dispatch facade for command-group extraction tests."""

from __future__ import annotations

from typing import Sequence

from .parser import CommandSnapshot, classify_command


def dispatch_command_name(argv: Sequence[str]) -> str:
    return classify_command(argv).command_name


__all__ = ("CommandSnapshot", "classify_command", "dispatch_command_name")
