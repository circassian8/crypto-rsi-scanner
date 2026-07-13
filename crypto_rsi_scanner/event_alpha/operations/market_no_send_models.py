"""Small value objects for guarded market/no-send operations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SAFETY_COUNTERS = {
    "trades_created": 0,
    "paper_trades_created": 0,
    "normal_rsi_signal_rows_written": 0,
    "triggered_fade_created": 0,
    "telegram_sends": 0,
}


class MarketNoSendError(RuntimeError):
    """A concise, credential-free market generation failure."""


@dataclass(frozen=True)
class MarketNoSendReadiness:
    status: str
    provider: str
    live_provider_authorized: bool
    provider_call_attempted: bool
    fixture_mode: bool
    no_send: bool
    research_only: bool
    top_n: int
    fetch_limit: int
    artifact_namespace: str
    reasons: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        payload["ready"] = self.ready
        return payload


@dataclass(frozen=True)
class MarketNoSendGenerationResult:
    status: str
    profile: str
    artifact_namespace: str
    namespace_dir: Path | None
    data_mode: str
    provider: str
    observed_at: str
    live_provider_authorized: bool
    provider_call_attempted: bool
    provider_request_succeeded: bool
    raw_market_rows: int = 0
    selected_market_rows: int = 0
    market_anomalies: int = 0
    candidates: int = 0
    core_rows: int = 0
    cards: int = 0
    run_id: str | None = None
    request_cache_path: Path | None = None
    manifest_path: Path | None = None
    failure_class: str | None = None

    @property
    def complete(self) -> bool:
        return self.status == "complete"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["namespace_dir"] = str(self.namespace_dir) if self.namespace_dir else None
        payload["request_cache_path"] = str(self.request_cache_path) if self.request_cache_path else None
        payload["manifest_path"] = str(self.manifest_path) if self.manifest_path else None
        payload["complete"] = self.complete
        payload.update(SAFETY_COUNTERS)
        payload.update({"no_send": True, "research_only": True, "pointer_published": False})
        return payload


__all__ = (
    "MarketNoSendError",
    "MarketNoSendGenerationResult",
    "MarketNoSendReadiness",
    "SAFETY_COUNTERS",
)
