"""Split implementation for `crypto_rsi_scanner/cli/services/event_alpha_notifications.py` (bindings)."""

from __future__ import annotations

import logging
from types import ModuleType
from typing import Any, MutableMapping

log = logging.getLogger(__name__)
_SERVICE_FUNCTION_NAMES = (
    'bind_scanner_globals',
    '_refresh_scanner_globals',
    '_event_alpha_notify_cycle_body',
    '_scanner_call',
    'event_alpha_notify_preview',
    'event_alpha_notify_preview_from_artifacts',
    'event_alpha_notify_go_no_go',
    'event_alpha_export_notification_pack',
    'event_alpha_notify_fixture_smoke',
    'event_alpha_send_readiness_report',
    'event_alpha_telegram_final_check_report',
    'event_alpha_notification_deliveries_report',
    'event_alpha_notification_runs_report',
)
def bind_scanner_globals(target: MutableMapping[str, object], scanner_module: ModuleType | None = None) -> ModuleType:
    if scanner_module is None:
        from .... import scanner as scanner_module
    for name, value in vars(scanner_module).items():
        if not name.startswith("__") and name not in _SERVICE_FUNCTION_NAMES:
            target[name] = value
    return scanner_module
def _refresh_scanner_globals() -> ModuleType:
    return bind_scanner_globals(globals())
def _scanner_call(function_name: str, /, *args: Any, **kwargs: Any) -> Any:
    from .... import scanner as scanner_module

    return getattr(scanner_module, function_name)(*args, **kwargs)
