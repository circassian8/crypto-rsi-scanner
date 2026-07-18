"""Errors for immutable Bybit execution-quality captures."""


class BybitExecutionQualityCaptureError(RuntimeError):
    """Raised when execution-quality evidence cannot be sealed or validated."""


__all__ = ("BybitExecutionQualityCaptureError",)
