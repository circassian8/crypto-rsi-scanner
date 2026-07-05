"""Execution phases for Event Alpha artifact doctor runs."""

from __future__ import annotations

from typing import Any

from . import artifact_doctor_core as _api
from .aggregation import aggregate_doctor_results
from .context import DoctorContext, build_doctor_context
from .discovery import discover_namespace_artifacts, load_artifact_indexes


def run_schema_checks(context: DoctorContext) -> DoctorContext:
    return context


def run_safety_checks(context: DoctorContext) -> DoctorContext:
    return context


def run_notification_checks(context: DoctorContext) -> DoctorContext:
    return context


def run_integrated_radar_checks(context: DoctorContext) -> DoctorContext:
    return context


def run_source_coverage_checks(context: DoctorContext) -> DoctorContext:
    return context


def run_provider_readiness_checks(context: DoctorContext) -> DoctorContext:
    return context


def run_outcome_checks(context: DoctorContext) -> DoctorContext:
    return context


def run_namespace_lifecycle_checks(context: DoctorContext) -> DoctorContext:
    return context


def diagnose_artifacts(*args: Any, **kwargs: Any) -> Any:
    """Run the artifact doctor through explicit phases.

    The phases are intentionally side-effect neutral in this pass; the legacy
    core remains the source of behavior until each category is migrated behind
    regression coverage.
    """

    context = build_doctor_context(*args, **kwargs)
    context = discover_namespace_artifacts(context)
    context = load_artifact_indexes(context)
    context = run_namespace_lifecycle_checks(context)
    context = run_schema_checks(context)
    context = run_safety_checks(context)
    context = run_notification_checks(context)
    context = run_integrated_radar_checks(context)
    context = run_source_coverage_checks(context)
    context = run_provider_readiness_checks(context)
    context = run_outcome_checks(context)
    result = _api.diagnose_artifacts(*context.args, **context.kwargs)
    return aggregate_doctor_results(result)
