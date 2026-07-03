"""Parser Integrated Radar parser extension point."""

from __future__ import annotations

import argparse


def add_integrated_radar_args(parser: argparse.ArgumentParser) -> None:
    """Compatibility extension point; flags remain owned by parser_event_alpha for now."""
    return None
