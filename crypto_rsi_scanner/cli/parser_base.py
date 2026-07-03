"""Base parser construction for the CLI facade."""

from __future__ import annotations

import argparse


def build_base_parser() -> argparse.ArgumentParser:
    """Create the shared scanner argument parser shell."""
    return argparse.ArgumentParser(
        description="Top-N crypto multi-timeframe RSI overextension scanner."
    )
