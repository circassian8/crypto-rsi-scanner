"""Evidence acquisition report renderer."""

from __future__ import annotations

from .acquisition_api import format_acquisition_report
from .models import *  # noqa: F403 - split modules share legacy model names

__all__ = ("format_acquisition_report",)
