"""Aggregation and status helpers for Event Alpha doctor results."""

from __future__ import annotations

from typing import Any

from .status import DoctorStatus


def aggregate_doctor_results(result: Any) -> Any:
    """Return the compatibility-preserving aggregate result unchanged."""

    return result


def determine_doctor_status(result: Any) -> str:
    """Calculate the public status from a result-like object."""

    blockers = tuple(getattr(result, "blockers", ()) or ())
    warnings = tuple(getattr(result, "warnings", ()) or ())
    if blockers:
        return DoctorStatus.BLOCKED.value
    status = str(getattr(result, "status", "") or "").upper()
    if status == DoctorStatus.STALE.value:
        return DoctorStatus.STALE.value
    if warnings:
        return DoctorStatus.WARN.value
    return DoctorStatus.OK.value
