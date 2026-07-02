"""Safety check plugin placeholder for migrated doctor checks."""

from __future__ import annotations

from ._utils import Messages


def apply_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    """Schema-backed safety checks currently run in safety_doctor."""
    return None
