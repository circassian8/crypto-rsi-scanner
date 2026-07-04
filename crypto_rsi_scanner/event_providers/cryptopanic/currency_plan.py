"""CryptoPanic currency request planning model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CryptoPanicCurrencyPlan:
    accepted: tuple[str, ...]
    rejected: tuple[dict[str, str], ...]
    duplicate_count: int = 0


__all__ = ("CryptoPanicCurrencyPlan",)
