"""Cross-artifact consistency phase facade for Event Alpha artifact doctor.

The current consistency implementation still lives in the compatibility
monolith. This module gives the execution pipeline a typed phase boundary so
checks can move here incrementally without changing CLI behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConsistencyDoctorResult:
    legacy_checks_ran: bool = True
    legacy_checks_skipped: bool = False
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def skipped_result() -> ConsistencyDoctorResult:
    return ConsistencyDoctorResult(legacy_checks_ran=False, legacy_checks_skipped=True)
