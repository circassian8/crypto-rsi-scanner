"""Public Event Alpha artifact doctor entrypoint.

The compatibility-heavy implementation remains in ``legacy_artifact_doctor``
while the public API is routed through focused doctor modules. Keep this module
as a thin orchestrator/export surface so new logic lands in the package modules.
"""

from __future__ import annotations

from . import legacy_artifact_doctor as _legacy
from .execution import diagnose_artifacts
from .report_sections.summary import format_artifact_doctor_report
from .result import EventAlphaArtifactDoctorResult

_OVERRIDES = {
    "diagnose_artifacts": diagnose_artifacts,
    "format_artifact_doctor_report": format_artifact_doctor_report,
    "EventAlphaArtifactDoctorResult": EventAlphaArtifactDoctorResult,
}

for _name in dir(_legacy):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    if _name in _OVERRIDES:
        continue
    globals()[_name] = getattr(_legacy, _name)

globals().update(_OVERRIDES)

__all__ = tuple(
    sorted(
        {
            *(
                name
                for name in dir(_legacy)
                if not (name.startswith("__") and name.endswith("__"))
            ),
            *_OVERRIDES,
        }
    )
)
