"""Event discovery compatibility surface."""

from __future__ import annotations

from . import loader as _loader
from . import legacy as _legacy

for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)


def _sync_legacy_overrides() -> None:
    classifier = globals().get("classify_event_asset", _legacy.classify_event_asset)
    _legacy.classify_event_asset = classifier
    _loader.classify_event_asset = classifier


def run_discovery(*args, **kwargs):
    _sync_legacy_overrides()
    return _legacy.run_discovery(*args, **kwargs)


def run_manual_discovery(*args, **kwargs):
    _sync_legacy_overrides()
    return _legacy.run_manual_discovery(*args, **kwargs)


__all__ = tuple(_name for _name in globals() if not _name.startswith("_"))
