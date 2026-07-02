"""Event Alpha provider preflight services.

These wrappers intentionally call the historical scanner command bodies until
the next scanner extraction pass moves the implementations behind direct
imports. Keeping the wrapper layer explicit lets dispatch tests target the
service package without changing provider guard behavior.
"""

from __future__ import annotations

from typing import Any


def _scanner_call(function_name: str, /, *args: Any, **kwargs: Any) -> Any:
    from ... import scanner as scanner_module

    return getattr(scanner_module, function_name)(*args, **kwargs)


def event_alpha_provider_health_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_provider_health_report", *args, **kwargs)


def event_alpha_cryptopanic_preflight(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_cryptopanic_preflight", *args, **kwargs)


def event_alpha_live_provider_readiness_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_live_provider_readiness_report", *args, **kwargs)


def event_alpha_dex_onchain_readiness_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_dex_onchain_readiness_report", *args, **kwargs)


def event_alpha_unlock_calendar_preflight_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_unlock_calendar_preflight_report", *args, **kwargs)


def event_alpha_coinalyze_preflight_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_coinalyze_preflight_report", *args, **kwargs)


def event_alpha_coinalyze_no_send_rehearsal(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_coinalyze_no_send_rehearsal", *args, **kwargs)


def event_alpha_bybit_announcements_preflight_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_bybit_announcements_preflight_report", *args, **kwargs)


def event_alpha_bybit_announcements_no_send_rehearsal(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_bybit_announcements_no_send_rehearsal", *args, **kwargs)


def event_alpha_provider_health_reset(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_provider_health_reset", *args, **kwargs)


__all__ = (
    "event_alpha_provider_health_report",
    "event_alpha_cryptopanic_preflight",
    "event_alpha_live_provider_readiness_report",
    "event_alpha_dex_onchain_readiness_report",
    "event_alpha_unlock_calendar_preflight_report",
    "event_alpha_coinalyze_preflight_report",
    "event_alpha_coinalyze_no_send_rehearsal",
    "event_alpha_bybit_announcements_preflight_report",
    "event_alpha_bybit_announcements_no_send_rehearsal",
    "event_alpha_provider_health_reset",
)
