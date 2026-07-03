"""Artifact discovery phase hooks for the Event Alpha doctor."""

from __future__ import annotations

from .context import DoctorContext


def discover_namespace_artifacts(context: DoctorContext) -> DoctorContext:
    """Resolve namespace-level artifact inputs.

    The legacy core still performs the concrete loading so current semantics and
    monkeypatch points remain unchanged during this refactor pass.
    """

    return context


def load_artifact_indexes(context: DoctorContext) -> DoctorContext:
    """Load derived artifact indexes for downstream checks."""

    return context
