"""Optional OpenAI Responses API provider for shadow relationship analysis."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from crypto_rsi_scanner.event_alpha.radar.llm.models import (
    ASSET_ROLE_VALUES,
    RECOMMENDED_ALERT_ACTION_VALUES,
    RELATIONSHIP_TYPE_VALUES,
)
from crypto_rsi_scanner.event_alpha.radar.llm.extraction_models import (
    ASSET_MENTION_TYPE_VALUES,
    CATALYST_TYPE_VALUES,
)
from crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames import structured_output_schema as _catalyst_frame_schema
from .base import LLMProviderResult

log = logging.getLogger(__name__)


def initialize_openai_provider(
    self: Any,
    *,
    api_key: str,
    model: str | None = None,
    prompt_version: str,
    timeout: float = 30.0,
    base_url: str = "https://api.openai.com/v1/responses",
    opener=urlopen,
) -> None:
    self.api_key = api_key
    self.model = model or "gpt-4.1-mini"
    self.prompt_version = prompt_version
    self.timeout = timeout
    self.base_url = base_url
    self.opener = opener


def analyze_openai_relationship(self: Any, packet: Mapping[str, Any]) -> LLMProviderResult:
    if not self.api_key:
        return LLMProviderResult(warning="OpenAI LLM relationship provider skipped: missing OPENAI_API_KEY")
    return _call_openai_json(
        self,
        request_payload=build_relationship_request_payload(self, packet),
        empty_warning="OpenAI LLM relationship provider returned no output text",
        failure_prefix="OpenAI LLM relationship provider failed",
    )


def analyze_openai_catalyst_frames(self: Any, packet: Mapping[str, Any]) -> LLMProviderResult:
    if not self.api_key:
        return LLMProviderResult(warning="OpenAI LLM catalyst-frame provider skipped: missing OPENAI_API_KEY")
    return _call_openai_json(
        self,
        request_payload=build_catalyst_frame_request_payload(self, packet),
        empty_warning="OpenAI LLM catalyst-frame provider returned no output text",
        failure_prefix="OpenAI LLM catalyst-frame provider failed",
    )


def extract_openai_raw_event(self: Any, packet: Mapping[str, Any]) -> LLMProviderResult:
    if not self.api_key:
        return LLMProviderResult(warning="OpenAI LLM extraction provider skipped: missing OPENAI_API_KEY")
    return _call_openai_json(
        self,
        request_payload=build_extraction_request_payload(self, packet),
        empty_warning="OpenAI LLM extraction provider returned no output text",
        failure_prefix="OpenAI LLM extraction provider failed",
    )


def _call_openai_json(
    self: Any,
    *,
    request_payload: Mapping[str, Any],
    empty_warning: str,
    failure_prefix: str,
) -> LLMProviderResult:
    try:
        payload = json.dumps(request_payload, sort_keys=True).encode("utf-8")
        request = Request(
            self.base_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with self.opener(request, timeout=self.timeout) as response:
            status = int(getattr(response, "status", getattr(response, "code", 200)))
            if status >= 400:
                raise RuntimeError(f"HTTP {status}")
            body = json.loads(response.read().decode("utf-8"))
        text = _extract_response_text(body)
        if not text:
            return LLMProviderResult(warning=empty_warning)
        return LLMProviderResult(raw=json.loads(text))
    except HTTPError as exc:
        return LLMProviderResult(warning=f"{failure_prefix}: HTTP {exc.code}")
    except (URLError, TimeoutError, json.JSONDecodeError, OSError, RuntimeError) as exc:
        log.warning("%s: %s", failure_prefix, exc)
        return LLMProviderResult(warning=f"{failure_prefix}: {type(exc).__name__}")


def build_relationship_request_payload(self: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model": self.model,
        "input": _openai_input(_system_prompt(self.prompt_version), packet),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "event_relationship_analysis",
                "strict": True,
                "schema": _analysis_schema(),
            }
        },
    }


def build_catalyst_frame_request_payload(self: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model": self.model,
        "input": _openai_input(_catalyst_frame_system_prompt(self.prompt_version), packet),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "event_catalyst_frame_analysis",
                "strict": True,
                "schema": _catalyst_frame_schema(),
            }
        },
    }


def build_extraction_request_payload(self: Any, packet: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model": self.model,
        "input": _openai_input(_extraction_system_prompt(self.prompt_version), packet),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "event_raw_extraction",
                "strict": True,
                "schema": _extraction_schema(),
            }
        },
    }


def _openai_input(system_text: str, packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": system_text}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": json.dumps(packet, sort_keys=True, default=str)}],
        },
    ]


def _system_prompt(prompt_version: str) -> str:
    return (
        f"Prompt version: {prompt_version}.\n"
        "You classify crypto event-discovery evidence. You do not recommend trades, "
        "position sizes, entries, exits, paper trades, or alert routing. Classify only "
        "the relationship between the source evidence, external catalyst, and crypto asset. "
        "Use evidence quotes copied exactly from the packet text. If source evidence is weak, "
        "choose store_only and explain the ambiguity."
    )


def _extraction_system_prompt(prompt_version: str) -> str:
    return (
        f"Prompt version: {prompt_version}.\n"
        "Extract raw crypto event-discovery evidence. You do not recommend trades, "
        "position sizes, alerts, paper trades, or execution. Identify external catalysts, "
        "crypto assets/projects actually mentioned, false-positive terms such as publisher "
        "names or ordinary words, and event date hints. Use exact quotes copied from the "
        "packet text. If evidence is weak, lower confidence and explain the ambiguity."
    )


def _catalyst_frame_system_prompt(prompt_version: str) -> str:
    return (
        f"Prompt version: {prompt_version}.\n"
        "Parse source evidence into catalyst frames. Separate the main catalyst from "
        "background, historical, corrective, negated, side-note, and market-reaction "
        "context. You do not recommend trades, alerts, paper trades, position sizes, "
        "or execution. Use exact source quotes. If a quote does not support a frame, "
        "lower confidence and put it in manual verification instead of promoting it."
    )


def _analysis_schema() -> dict[str, Any]:
    quote_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "source_field": {"type": "string"},
            "supports": {"type": "string"},
        },
        "required": ["text", "source_field", "supports"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "asset_role": {"type": "string", "enum": sorted(ASSET_ROLE_VALUES)},
            "relationship_type": {"type": "string", "enum": sorted(RELATIONSHIP_TYPE_VALUES)},
            "recommended_alert_action": {
                "type": "string",
                "enum": sorted(RECOMMENDED_ALERT_ACTION_VALUES),
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
            "evidence_quotes": {"type": "array", "items": quote_schema},
            "external_catalyst": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": ["string", "null"]},
                    "catalyst_type": {"type": "string"},
                    "event_time": {"type": ["string", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_quotes": {"type": "array", "items": quote_schema},
                },
                "required": ["name", "catalyst_type", "event_time", "confidence", "evidence_quotes"],
            },
            "source_quality": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source_origin": {"type": ["string", "null"]},
                    "source_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "timing_quality": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["source_origin", "source_confidence", "timing_quality", "notes"],
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "asset_role",
            "relationship_type",
            "recommended_alert_action",
            "confidence",
            "reason",
            "evidence_quotes",
            "external_catalyst",
            "source_quality",
            "warnings",
        ],
    }


def _extraction_schema() -> dict[str, Any]:
    quote_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "source_field": {"type": "string"},
            "supports": {"type": "string"},
        },
        "required": ["text", "source_field", "supports"],
    }
    catalyst_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": ["string", "null"]},
            "catalyst_type": {"type": "string", "enum": sorted(CATALYST_TYPE_VALUES)},
            "event_time": {"type": ["string", "null"]},
            "event_time_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_quotes": {"type": "array", "items": quote_schema},
        },
        "required": ["name", "catalyst_type", "event_time", "event_time_confidence", "confidence", "evidence_quotes"],
    }
    asset_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": ["string", "null"]},
            "symbol": {"type": ["string", "null"]},
            "coin_id": {"type": ["string", "null"]},
            "contract_address": {"type": ["string", "null"]},
            "mention_type": {"type": "string", "enum": sorted(ASSET_MENTION_TYPE_VALUES)},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_quotes": {"type": "array", "items": quote_schema},
        },
        "required": ["name", "symbol", "coin_id", "contract_address", "mention_type", "confidence", "evidence_quotes"],
    }
    false_positive_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "reason": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_quotes": {"type": "array", "items": quote_schema},
        },
        "required": ["text", "reason", "confidence", "evidence_quotes"],
    }
    date_hint_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "parsed_event_time": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence_quotes": {"type": "array", "items": quote_schema},
        },
        "required": ["text", "parsed_event_time", "confidence", "evidence_quotes"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "external_catalysts": {"type": "array", "items": catalyst_schema},
            "crypto_asset_mentions": {"type": "array", "items": asset_schema},
            "false_positive_terms": {"type": "array", "items": false_positive_schema},
            "event_date_hints": {"type": "array", "items": date_hint_schema},
            "suggested_followup_queries": {"type": "array", "items": {"type": "string"}},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "confidence",
            "external_catalysts",
            "crypto_asset_mentions",
            "false_positive_terms",
            "event_date_hints",
            "suggested_followup_queries",
            "warnings",
        ],
    }


def _extract_response_text(body: Mapping[str, Any]) -> str:
    direct = body.get("output_text")
    if isinstance(direct, str):
        return direct
    for output in body.get("output", []) if isinstance(body.get("output"), list) else []:
        if not isinstance(output, Mapping):
            continue
        for content in output.get("content", []) if isinstance(output.get("content"), list) else []:
            if not isinstance(content, Mapping):
                continue
            text = content.get("text")
            if isinstance(text, str):
                return text
    return ""
