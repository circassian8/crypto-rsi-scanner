"""Status helpers for Event Alpha artifact doctor runs."""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class DoctorStatus(str, Enum):
    OK = "OK"
    WARN = "WARN"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


def status_from_issues(
    *,
    blockers: Iterable[object] = (),
    warnings: Iterable[object] = (),
    stale: bool = False,
) -> DoctorStatus:
    if tuple(blockers):
        return DoctorStatus.BLOCKED
    if stale:
        return DoctorStatus.STALE
    if tuple(warnings):
        return DoctorStatus.WARN
    return DoctorStatus.OK
