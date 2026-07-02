"""Path hygiene checks for Event Alpha artifact-doctor output."""

from __future__ import annotations

from ._utils import Messages, ctx_mapping, ctx_value, emit


def apply_integrated_path_checks(ctx: object, blockers: Messages, warnings: Messages) -> None:
    """Emit integrated-radar path blockers from computed conflict counters."""
    strict = bool(ctx_value(ctx, "strict", False))
    integrated_conflicts = ctx_mapping(ctx, "integrated_conflicts")
    for key in (
        "integrated_delivery_card_path_absolute",
        "integrated_operator_markdown_absolute_path",
        "operator_structured_path_absolute",
    ):
        count = integrated_conflicts.get(key, 0)
        if count:
            emit(blockers, warnings, f"{key}={count}", blocker=strict)
