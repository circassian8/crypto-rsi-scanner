"""Fixture-backed LLM relationship provider for offline tests/evals."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

from .base import LLMProviderResult

log = logging.getLogger(__name__)


class FixtureLLMRelationshipProvider:
    name = "fixture"

    def __init__(self, path: str | Path | None = None, *, required: bool = False) -> None:
        self.path = Path(path).expanduser() if path else _default_fixture_path()
        self.required = required
        self._cases: dict[str, dict[str, Any]] | None = None

    def analyze_relationship(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        cases = self._load_cases()
        for key in _packet_keys(packet):
            raw = cases.get(key)
            if raw is not None:
                return LLMProviderResult(raw=dict(raw))
        return LLMProviderResult(warning=f"fixture LLM output not found for candidate {packet.get('candidate_key')}")

    def _load_cases(self) -> dict[str, dict[str, Any]]:
        if self._cases is not None:
            return self._cases
        if self.path is None or not self.path.exists():
            if self.required:
                raise FileNotFoundError(f"fixture LLM cases not found: {self.path}")
            log.warning("Fixture LLM cases missing: %s", self.path)
            self._cases = {}
            return self._cases
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            outputs = raw.get("llm_outputs", raw) if isinstance(raw, dict) else raw
            if not isinstance(outputs, list):
                raise ValueError("fixture LLM cases must be a list or {'llm_outputs': [...]}")
            cases: dict[str, dict[str, Any]] = {}
            for item in outputs:
                if not isinstance(item, Mapping):
                    raise ValueError("fixture LLM case entries must be objects")
                analysis = item.get("analysis") if isinstance(item.get("analysis"), Mapping) else item
                keys = _case_keys(item)
                if not keys:
                    raise ValueError("fixture LLM case missing case_id/event_id/coin_id/symbol")
                for key in keys:
                    cases[key] = dict(analysis)
            self._cases = cases
            return cases
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("Fixture LLM cases load failed: %s", exc)
            self._cases = {}
            return self._cases


class FixtureLLMExtractionProvider:
    name = "fixture"

    def __init__(self, path: str | Path | None = None, *, required: bool = False) -> None:
        self.path = Path(path).expanduser() if path else _default_extraction_fixture_path()
        self.required = required
        self._cases: dict[str, dict[str, Any]] | None = None

    def extract_raw_event(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        cases = self._load_cases()
        for key in _extraction_packet_keys(packet):
            raw = cases.get(key)
            if raw is not None:
                return LLMProviderResult(raw=dict(raw))
        return LLMProviderResult(warning=f"fixture LLM extraction not found for raw event {packet.get('raw_id')}")

    def _load_cases(self) -> dict[str, dict[str, Any]]:
        if self._cases is not None:
            return self._cases
        if self.path is None or not self.path.exists():
            if self.required:
                raise FileNotFoundError(f"fixture LLM extraction cases not found: {self.path}")
            log.warning("Fixture LLM extraction cases missing: %s", self.path)
            self._cases = {}
            return self._cases
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            outputs = raw.get("llm_extractions", raw) if isinstance(raw, dict) else raw
            if not isinstance(outputs, list):
                raise ValueError("fixture LLM extraction cases must be a list or {'llm_extractions': [...]}")
            cases: dict[str, dict[str, Any]] = {}
            for item in outputs:
                if not isinstance(item, Mapping):
                    raise ValueError("fixture LLM extraction entries must be objects")
                extraction = item.get("extraction") if isinstance(item.get("extraction"), Mapping) else item
                keys = _extraction_case_keys(item)
                if not keys:
                    raise ValueError("fixture LLM extraction case missing case_id/raw_id")
                for key in keys:
                    cases[key] = dict(extraction)
            self._cases = cases
            return cases
        except Exception as exc:  # noqa: BLE001
            if self.required:
                raise
            log.warning("Fixture LLM extraction load failed: %s", exc)
            self._cases = {}
            return self._cases


def _default_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "event_discovery" / "llm_golden_cases.json"


def _default_extraction_fixture_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "event_discovery" / "llm_extraction_golden_cases.json"


def _case_keys(item: Mapping[str, Any]) -> tuple[str, ...]:
    raw_keys = (
        item.get("case_id"),
        item.get("candidate_key"),
        _candidate_key(item.get("event_id"), item.get("coin_id")),
        _candidate_key(item.get("event_id"), item.get("symbol")),
        item.get("event_id"),
        item.get("coin_id"),
        item.get("symbol"),
    )
    return tuple(str(key) for key in raw_keys if key)


def _packet_keys(packet: Mapping[str, Any]) -> tuple[str, ...]:
    event = packet.get("event") if isinstance(packet.get("event"), Mapping) else {}
    asset = packet.get("asset") if isinstance(packet.get("asset"), Mapping) else {}
    raw_keys = (
        packet.get("case_id"),
        packet.get("candidate_key"),
        _candidate_key(event.get("event_id"), asset.get("coin_id")),
        _candidate_key(event.get("event_id"), asset.get("symbol")),
        event.get("event_id"),
        asset.get("coin_id"),
        asset.get("symbol"),
    )
    return tuple(str(key) for key in raw_keys if key)


def _candidate_key(event_id: object, asset_id: object) -> str | None:
    if not event_id or not asset_id:
        return None
    return f"{event_id}:{asset_id}"


def _extraction_case_keys(item: Mapping[str, Any]) -> tuple[str, ...]:
    raw_keys = (
        item.get("case_id"),
        item.get("raw_id"),
        item.get("source_url"),
    )
    return tuple(str(key) for key in raw_keys if key)


def _extraction_packet_keys(packet: Mapping[str, Any]) -> tuple[str, ...]:
    raw_keys = (
        packet.get("case_id"),
        packet.get("raw_id"),
        packet.get("source_url"),
    )
    return tuple(str(key) for key in raw_keys if key)
