"""Core opportunity card-link helpers."""

from __future__ import annotations

from .store_api import update_core_opportunity_card_links
from .models import *  # noqa: F403 - split modules share legacy model names

__all__ = ("update_core_opportunity_card_links",)
