"""Event Alpha namespace lifecycle services.

Namespace command bodies remain scanner-owned for this pass. The service layer
is still useful because command dispatch can depend on package services while
the later scanner-size pass moves implementation code safely.
"""

from __future__ import annotations

from typing import Any


def _scanner_call(function_name: str, /, *args: Any, **kwargs: Any) -> Any:
    from ... import scanner as scanner_module

    return getattr(scanner_module, function_name)(*args, **kwargs)


def event_alpha_mark_namespace_stale(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_mark_namespace_stale", *args, **kwargs)


def event_alpha_mark_known_stale_namespaces(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_mark_known_stale_namespaces", *args, **kwargs)


def event_alpha_prune_or_archive_stale_namespace(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_prune_or_archive_stale_namespace", *args, **kwargs)


def event_alpha_namespace_lifecycle_report(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_namespace_lifecycle_report", *args, **kwargs)


def event_alpha_list_active_namespaces(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_list_active_namespaces", *args, **kwargs)


def event_alpha_archive_stale_namespaces(*args: Any, **kwargs: Any) -> Any:
    return _scanner_call("event_alpha_archive_stale_namespaces", *args, **kwargs)


__all__ = (
    "event_alpha_mark_namespace_stale",
    "event_alpha_mark_known_stale_namespaces",
    "event_alpha_prune_or_archive_stale_namespace",
    "event_alpha_namespace_lifecycle_report",
    "event_alpha_list_active_namespaces",
    "event_alpha_archive_stale_namespaces",
)
