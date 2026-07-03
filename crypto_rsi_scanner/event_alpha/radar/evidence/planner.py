"""Evidence acquisition planning compatibility surface."""

from __future__ import annotations

from .legacy_acquisition import EvidenceAcquisitionRequest
from .models import *  # noqa: F403 - split modules share legacy model names

__all__ = ("EvidenceAcquisitionRequest",)
