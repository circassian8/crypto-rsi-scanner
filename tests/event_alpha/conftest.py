"""Pytest isolation for split Event Alpha tests."""

from __future__ import annotations

import copy

import pytest


@pytest.fixture(autouse=True)
def restore_event_alpha_config_state():
    from crypto_rsi_scanner import config

    original = {}
    for name in dir(config):
        if not name.isupper():
            continue
        value = getattr(config, name)
        try:
            original[name] = copy.deepcopy(value)
        except Exception:  # noqa: BLE001
            original[name] = value

    yield

    for name in tuple(dir(config)):
        if name.isupper() and name not in original:
            delattr(config, name)
    for name, value in original.items():
        setattr(config, name, value)
