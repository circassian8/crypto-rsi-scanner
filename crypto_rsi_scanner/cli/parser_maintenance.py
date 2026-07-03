"""Parser Maintenance parser extension point."""

from __future__ import annotations

import argparse


def add_maintenance_args(parser: argparse.ArgumentParser) -> None:
    """Compatibility extension point; flags remain owned by parser_event_alpha for now."""
    return None
