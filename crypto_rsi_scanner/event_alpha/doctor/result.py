"""Result aggregate for Event Alpha artifact doctor runs.

The concrete dataclass is aliased to the behavior-compatible core to preserve constructor
compatibility, direct attribute access, ``to_dict``/``from_dict``, and mutation
helpers while command behavior is migrated into smaller modules.
"""

from __future__ import annotations

from .artifact_doctor_core import EventAlphaArtifactDoctorResult

__all__ = ("EventAlphaArtifactDoctorResult",)
