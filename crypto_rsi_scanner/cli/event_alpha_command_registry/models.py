"""Split implementation for `crypto_rsi_scanner/cli/event_alpha_command_registry.py` (models)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from .._scanner_bindings import bind_scanner_globals
from ..services import (
    event_alpha_integrated as _service_integrated,
    event_alpha_namespace as _service_namespace,
    event_alpha_notifications as _service_notifications,
    event_alpha_outcomes as _service_outcomes,
    event_alpha_provider_preflights as _service_provider_preflights,
    event_alpha_reports as _service_reports,
    event_alpha_research as _service_research,
)

@dataclass(frozen=True)
class EventAlphaCommandRegistration:
    command_flag: str
    parsed_attr: str
    handler_module: str
    handler_name: str
    command_group: str
    requires_no_send: bool = True
    allows_live_provider_call: bool = False
    test_fixture_command: bool = False
    safety_notes: str = "research-only; no live calls or Telegram sends by default"
