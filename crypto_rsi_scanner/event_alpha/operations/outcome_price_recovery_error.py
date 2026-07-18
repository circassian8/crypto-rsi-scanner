"""Closed error type for guarded historical outcome-price recovery."""

from __future__ import annotations


class OutcomePriceRecoveryError(RuntimeError):
    """Closed recovery failure without provider payload or secret leakage."""

    def __init__(
        self,
        reason_code: str,
        *,
        http_status: int | None = None,
        request_count: int = 0,
    ) -> None:
        self.reason_code = _safe_code(reason_code)
        self.http_status = (
            http_status
            if isinstance(http_status, int) and 100 <= http_status <= 599
            else None
        )
        self.request_count = max(0, int(request_count))
        super().__init__(self.reason_code)


def _safe_code(value: object) -> str:
    text = str(value or "unknown").strip().casefold()
    cleaned = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in text
    )
    return cleaned[:96] or "unknown"


__all__ = ("OutcomePriceRecoveryError",)
