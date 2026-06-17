"""Optional OpenAI Responses API provider for shadow relationship analysis."""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..event_llm_models import (
    ASSET_ROLE_VALUES,
    RECOMMENDED_ALERT_ACTION_VALUES,
    RELATIONSHIP_TYPE_VALUES,
)
from .base import LLMProviderResult

log = logging.getLogger(__name__)


class OpenAILLMRelationshipProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str | None = None,
        prompt_version: str = "llm_proxy_context_v1",
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

    def analyze_relationship(self, packet: Mapping[str, Any]) -> LLMProviderResult:
        if not self.api_key:
            return LLMProviderResult(warning="OpenAI LLM relationship provider skipped: missing OPENAI_API_KEY")
        try:
            payload = json.dumps(self._request_payload(packet), sort_keys=True).encode("utf-8")
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
                return LLMProviderResult(warning="OpenAI LLM relationship provider returned no output text")
            return LLMProviderResult(raw=json.loads(text))
        except HTTPError as exc:
            return LLMProviderResult(warning=f"OpenAI LLM relationship provider failed: HTTP {exc.code}")
        except (URLError, TimeoutError, json.JSONDecodeError, OSError, RuntimeError) as exc:
            log.warning("OpenAI LLM relationship provider failed: %s", exc)
            return LLMProviderResult(warning=f"OpenAI LLM relationship provider failed: {type(exc).__name__}")

    def _request_payload(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [{
                        "type": "input_text",
                        "text": _system_prompt(self.prompt_version),
                    }],
                },
                {
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": json.dumps(packet, sort_keys=True, default=str),
                    }],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "event_relationship_analysis",
                    "strict": True,
                    "schema": _analysis_schema(),
                }
            },
        }


def _system_prompt(prompt_version: str) -> str:
    return (
        f"Prompt version: {prompt_version}.\n"
        "You classify crypto event-discovery evidence. You do not recommend trades, "
        "position sizes, entries, exits, paper trades, or alert routing. Classify only "
        "the relationship between the source evidence, external catalyst, and crypto asset. "
        "Use evidence quotes copied exactly from the packet text. If source evidence is weak, "
        "choose store_only and explain the ambiguity."
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
