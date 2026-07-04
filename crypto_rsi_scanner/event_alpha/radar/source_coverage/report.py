"""Split implementation for `crypto_rsi_scanner/event_alpha/radar/source_coverage.py` (report)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from .... import event_provider_status
from ....event_providers import cryptopanic as cryptopanic_provider
from ...artifacts import paths as event_artifact_paths
from ...providers import bybit_announcements_preflight as event_bybit_announcements_preflight
from ...providers import coinalyze_preflight as event_coinalyze_preflight
from ...providers import dex_onchain_readiness as event_dex_onchain_readiness
from ...providers import official_exchange_activation as event_official_exchange_activation
from ...providers import provider_health as event_provider_health
from ...providers import source_packs as event_source_packs
from ...providers import unlock_calendar_preflight as event_unlock_calendar_preflight
from .models import *  # noqa: F403

# Intentionally empty split module.
