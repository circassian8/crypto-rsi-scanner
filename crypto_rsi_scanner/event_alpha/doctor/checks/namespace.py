"""Namespace lifecycle check plugin placeholder for migrated doctor checks."""

from __future__ import annotations

from ._utils import Messages


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    """Namespace lifecycle checks currently run in namespace_doctor."""
    return None
