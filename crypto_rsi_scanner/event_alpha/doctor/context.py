"""Context construction for Event Alpha artifact doctor runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DoctorContext:
    """Immutable call context passed between doctor orchestration phases."""

    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)

    def keyword(self, name: str, default: Any = None) -> Any:
        return self.kwargs.get(name, default)


def build_doctor_context(*args: Any, **kwargs: Any) -> DoctorContext:
    """Capture the public ``diagnose_artifacts`` call without changing inputs."""

    return DoctorContext(args=tuple(args), kwargs=dict(kwargs))
