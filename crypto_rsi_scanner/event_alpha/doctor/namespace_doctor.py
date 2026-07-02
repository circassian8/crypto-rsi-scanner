"""Namespace lifecycle phase for Event Alpha artifact doctor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..namespace import status as event_alpha_namespace_status


@dataclass(frozen=True)
class NamespaceDoctorResult:
    namespace_dir: Path | None
    namespace_status: str | None = None
    namespace_stale_deprecated: int = 0
    namespace_superseded_by: Any | None = None
    short_circuit: bool = False
    warnings: tuple[str, ...] = ()


def inspect_namespace(
    namespace_dir: str | Path | None,
    *,
    include_stale_artifacts: bool = False,
) -> NamespaceDoctorResult:
    """Read namespace lifecycle status before artifact content checks run."""
    if namespace_dir is None:
        return NamespaceDoctorResult(namespace_dir=None, namespace_status=event_alpha_namespace_status.STATUS_ACTIVE)
    base = Path(namespace_dir)
    marker = event_alpha_namespace_status.load_namespace_status(base)
    is_stale = event_alpha_namespace_status.is_stale_deprecated(marker)
    warning = event_alpha_namespace_status.format_namespace_status(marker) if is_stale and marker else None
    return NamespaceDoctorResult(
        namespace_dir=base,
        namespace_status=marker.status if marker else event_alpha_namespace_status.STATUS_ACTIVE,
        namespace_stale_deprecated=1 if is_stale else 0,
        namespace_superseded_by=marker.superseded_by if marker else None,
        short_circuit=bool(is_stale and not include_stale_artifacts),
        warnings=(warning,) if warning else (),
    )
