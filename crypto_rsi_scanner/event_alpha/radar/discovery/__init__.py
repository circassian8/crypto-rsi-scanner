"""Event discovery compatibility surface."""

from __future__ import annotations

from . import loader as _loader
from . import api as _api

for _name in dir(_api):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_api, _name)


def _sync_api_overrides() -> None:
    classifier = globals().get("classify_event_asset", _api.classify_event_asset)
    _api.classify_event_asset = classifier
    _loader.classify_event_asset = classifier


def run_discovery(*args, **kwargs):
    _sync_api_overrides()
    return _api.run_discovery(*args, **kwargs)


def run_manual_discovery(*args, **kwargs):
    _sync_api_overrides()
    return _api.run_manual_discovery(*args, **kwargs)


__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))
