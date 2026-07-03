"""Summary report renderer for the Event Alpha artifact doctor."""

from __future__ import annotations

from .. import legacy_artifact_doctor as _legacy


def render_section(result: object) -> list[str]:
    return _legacy.format_artifact_doctor_report(result).splitlines()


def format_artifact_doctor_report(result: object) -> str:
    return "\n".join(render_section(result))
