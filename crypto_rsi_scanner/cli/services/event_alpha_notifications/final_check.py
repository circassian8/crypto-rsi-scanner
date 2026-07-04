"""Split implementation for `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` (final_check)."""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Any, MutableMapping
from .bindings import *  # noqa: F403

def event_alpha_telegram_final_check_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_telegram_final_check_report", *args, **kwargs)
