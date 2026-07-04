"""Compatibility exports for OpenAI LLM providers."""

from __future__ import annotations

from . import openai_support as _support
from .openai_extraction import OpenAILLMExtractionProvider
from .openai_relationship import OpenAILLMRelationshipProvider

for _name in dir(_support):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_support, _name)

__all__ = tuple(_name for _name in globals() if not _name.startswith("__"))
