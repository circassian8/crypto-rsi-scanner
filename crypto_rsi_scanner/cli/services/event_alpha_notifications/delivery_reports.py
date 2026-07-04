"""Split implementation for `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` (delivery_reports)."""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Any, MutableMapping
from .bindings import *  # noqa: F403

def event_alpha_notification_deliveries_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_notification_deliveries_report", *args, **kwargs)
def event_alpha_notification_runs_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_notification_runs_report", *args, **kwargs)
