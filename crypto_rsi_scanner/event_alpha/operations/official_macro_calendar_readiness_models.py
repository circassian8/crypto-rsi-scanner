"""Closed read-only models for official macro-calendar readiness."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class _OfficialMacroSourceReadiness:
    """One source's static eligibility without crossing the provider boundary."""

    source: str
    availability: str
    official_endpoint_configured: bool
    live_authorization_present: bool
    contact_required: bool
    contact_configured: bool | None
    request_eligible: bool
    provider_calls_during_readiness: int = 0
    maximum_provider_calls_if_acquire: int = 0
    reason_code: str | None = None


OfficialMacroSourceReadiness = _OfficialMacroSourceReadiness


@dataclass(frozen=True)
class _OfficialMacroReadiness:
    status: str
    current_status: str
    live_acquisition_authorized: bool
    contact_configured: bool
    source_readiness: tuple[_OfficialMacroSourceReadiness, ...] = ()
    live_partial_snapshot_eligible: bool = False
    local_import_partial_snapshot_supported: bool = True
    partial_snapshot_eligibility: str = ""
    local_import_command: str = ""
    local_import_requirements: tuple[str, ...] = ()
    read_only: bool = True
    provider_call_count: int = 0
    provider_call_attempted: bool = False
    writes_performed: bool = False
    provider_authorization_mutated: bool = False
    output_base: str = ""
    latest_attempt_status: str = "none"
    latest_success_status: str = "none"
    reason_codes: tuple[str, ...] = ()
    implications: tuple[str, ...] = ()
    next_safe_command: str = ""
    authorization_boundary: str = ""
    expected_provider_activity: str = ""
    rollback_disable_command: str = ""
    research_only: bool = True
    no_send: bool = True
    strict_alerts_created: int = 0
    telegram_sends: int = 0
    trades_created: int = 0
    paper_trades_created: int = 0
    normal_rsi_signal_rows_written: int = 0
    triggered_fade_created: int = 0

    @property
    def ready(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_readiness"] = [
            asdict(row) for row in self.source_readiness
        ]
        payload["reason_codes"] = list(self.reason_codes)
        payload["implications"] = list(self.implications)
        payload["local_import_requirements"] = list(
            self.local_import_requirements
        )
        payload["ready"] = self.ready
        return payload


OfficialMacroReadiness = _OfficialMacroReadiness


def build_official_macro_source_readiness(
    *,
    authorized: bool,
    contact_configured: bool,
) -> tuple[_OfficialMacroSourceReadiness, ...]:
    """Project per-source eligibility without provider, environment, or writes."""

    rows: list[_OfficialMacroSourceReadiness] = []
    for source in ("federal_reserve", "bea", "bls"):
        contact_required = source == "bls"
        contact_ready = contact_configured if contact_required else None
        request_eligible = authorized and (
            not contact_required or contact_configured
        )
        if request_eligible:
            availability = "available_for_authorized_acquisition"
            reason_code = None
        elif not authorized and contact_required and not contact_configured:
            availability = "blocked_missing_live_authorization_and_contact"
            reason_code = "live_authorization_and_bls_contact_missing"
        elif not authorized:
            availability = "configured_waiting_for_live_authorization"
            reason_code = "live_calendar_authorization_missing"
        else:
            availability = "missing_configuration"
            reason_code = "bls_contact_missing_or_invalid"
        rows.append(
            _OfficialMacroSourceReadiness(
                source=source,
                availability=availability,
                official_endpoint_configured=True,
                live_authorization_present=authorized,
                contact_required=contact_required,
                contact_configured=contact_ready,
                request_eligible=request_eligible,
                maximum_provider_calls_if_acquire=1 if request_eligible else 0,
                reason_code=reason_code,
            )
        )
    return tuple(rows)


__all__ = (
    "OfficialMacroReadiness",
    "OfficialMacroSourceReadiness",
    "build_official_macro_source_readiness",
)
