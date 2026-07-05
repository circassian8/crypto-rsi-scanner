"""Backtest CLI entrypoint exports."""

from __future__ import annotations

from .api import _validate_cli_args, main

__all__ = ("_validate_cli_args", "main")
