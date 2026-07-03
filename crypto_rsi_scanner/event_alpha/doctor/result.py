"""Result aggregate for Event Alpha artifact doctor runs.

The concrete dataclass is aliased to the legacy core to preserve constructor
compatibility, direct attribute access, ``to_dict``/``from_dict``, and mutation
helpers while command behavior is migrated into smaller modules.
"""

from __future__ import annotations

from .legacy_artifact_doctor import EventAlphaArtifactDoctorResult

__all__ = ("EventAlphaArtifactDoctorResult",)
