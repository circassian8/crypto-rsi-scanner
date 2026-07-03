"""Core opportunity store models."""

from __future__ import annotations

from .legacy_store import (
    CanonicalCoreOpportunityView,
    CoreEvidenceAcquisitionView,
    EventCoreOpportunityCardLinkUpdateResult,
    EventCoreOpportunityStoreConfig,
    EventCoreOpportunityStoreNormalizeResult,
    EventCoreOpportunityStoreReadResult,
    EventCoreOpportunityStoreWriteResult,
)
from ..core_opportunities import CoreOpportunity

__all__ = (
    "CanonicalCoreOpportunityView",
    "CoreEvidenceAcquisitionView",
    "CoreOpportunity",
    "EventCoreOpportunityCardLinkUpdateResult",
    "EventCoreOpportunityStoreConfig",
    "EventCoreOpportunityStoreNormalizeResult",
    "EventCoreOpportunityStoreReadResult",
    "EventCoreOpportunityStoreWriteResult",
)
