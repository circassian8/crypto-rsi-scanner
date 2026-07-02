"""Compatibility shim for :mod:`crypto_rsi_scanner.event_alpha.doctor.artifact_doctor`."""

from __future__ import annotations

from .event_alpha.doctor import artifact_doctor as _artifact_doctor

globals().update(
    {
        name: getattr(_artifact_doctor, name)
        for name in dir(_artifact_doctor)
        if not (name.startswith("__") and name.endswith("__"))
    }
)

__all__ = tuple(
    name
    for name in dir(_artifact_doctor)
    if not (name.startswith("__") and name.endswith("__"))
)
