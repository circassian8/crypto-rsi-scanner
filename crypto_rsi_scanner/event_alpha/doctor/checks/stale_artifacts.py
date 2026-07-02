"""Stale artifact check plugin placeholder for migrated doctor checks."""

from __future__ import annotations

from ._utils import Messages


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    """Stale artifact checks are still computed by the compatibility doctor."""
    return None
