"""CryptoPanic HTTP status error."""

from __future__ import annotations


class CryptoPanicHTTPStatusError(RuntimeError):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.status = int(status_code)
        self.code = int(status_code)


__all__ = ("CryptoPanicHTTPStatusError",)
