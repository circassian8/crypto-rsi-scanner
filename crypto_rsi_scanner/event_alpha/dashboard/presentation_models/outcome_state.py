"""Conservative presentation projection for persisted outcome states."""

from __future__ import annotations

from collections.abc import Mapping


_MATURED_STATES = frozenset({
    "complete",
    "completed",
    "filled",
    "graded",
    "mature",
    "matured",
    "resolved",
})
_PENDING_STATES = frozenset({
    "awaiting_data",
    "awaiting_horizon",
    "open",
    "pending",
    "scheduled",
})


def project_outcome_state(row: Mapping[str, object]) -> tuple[str, str]:
    """Return the exact display state and a conservative filter bucket.

    Explicit artifact states are never discarded. Known in-progress states map
    to ``pending`` and known completed states map to ``matured``. Every other
    explicit state, including unavailable-data and unknown future states, fails
    closed into the ``unavailable`` bucket while retaining its exact label.
    """

    explicit = str(
        row.get("outcome_status")
        or row.get("maturation_state")
        or ""
    ).strip().casefold()
    if explicit in _PENDING_STATES:
        return explicit, "pending"
    if explicit in _MATURED_STATES:
        return explicit, "matured"
    if explicit:
        return explicit, "unavailable"
    if (
        (row.get("outcome_label") or row.get("validation_label"))
        and row.get("outcome_evaluated_at")
    ):
        return "matured", "matured"
    return "pending", "pending"


__all__ = ("project_outcome_state",)
