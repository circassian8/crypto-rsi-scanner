"""Public Event Alpha artifact doctor entrypoint."""

from __future__ import annotations

from . import artifact_doctor_core as _api
from .execution import diagnose_artifacts
from .report_sections.summary import format_artifact_doctor_report
from .result import EventAlphaArtifactDoctorResult

_OVERRIDES = {
    "diagnose_artifacts": diagnose_artifacts,
    "format_artifact_doctor_report": format_artifact_doctor_report,
    "EventAlphaArtifactDoctorResult": EventAlphaArtifactDoctorResult,
}

for _name in dir(_api):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    if _name in _OVERRIDES:
        continue
    globals()[_name] = getattr(_api, _name)

globals().update(_OVERRIDES)

__all__ = tuple(
    sorted(
        {
            *(
                name
                for name in dir(_api)
                if not (name.startswith("__") and name.endswith("__"))
            ),
            *_OVERRIDES,
        }
    )
)
