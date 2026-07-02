"""Declarative Event Alpha doctor check registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DoctorCheck:
    check_id: str
    category: str
    severity: str
    schema_dependencies: tuple[str, ...]
    description: str
    introduced_in_schema_version: str


CHECKS: tuple[DoctorCheck, ...] = (
    DoctorCheck(
        check_id="schema.missing_required_fields",
        category="schema",
        severity="blocker",
        schema_dependencies=("row_type",),
        description="Rows must include schema-required fields before higher-order validation.",
        introduced_in_schema_version="event_alpha_schema_v1",
    ),
    DoctorCheck(
        check_id="schema.invalid_enum_fields",
        category="schema",
        severity="blocker",
        schema_dependencies=("opportunity_type", "final_level", "delivery_status", "status"),
        description="Enum-like fields must stay inside the schema-declared value sets.",
        introduced_in_schema_version="event_alpha_schema_v1",
    ),
    DoctorCheck(
        check_id="schema.invalid_path_fields",
        category="schema",
        severity="blocker",
        schema_dependencies=("path", "artifact_path", "card_path", "research_card_path", "notification_preview_path"),
        description="Operator artifact path fields must be relative unless explicitly marked debug absolute.",
        introduced_in_schema_version="event_alpha_schema_v1",
    ),
    DoctorCheck(
        check_id="safety.invalid_safety_fields",
        category="safety",
        severity="blocker",
        schema_dependencies=(
            "research_only",
            "no_send_rehearsal",
            "sent",
            "normal_rsi_signal_written",
            "triggered_fade_created",
            "trades_created",
            "paper_trades_created",
            "trade_created",
            "paper_trade_created",
        ),
        description="Research artifact rows must not claim sends or trading-side effects in guarded paths.",
        introduced_in_schema_version="event_alpha_schema_v1",
    ),
    DoctorCheck(
        check_id="namespace.stale_send_readiness",
        category="namespace",
        severity="blocker",
        schema_dependencies=("namespace", "status", "safe_for_send_readiness"),
        description="Stale namespaces cannot be used as send-readiness sources.",
        introduced_in_schema_version="event_alpha_schema_v1",
    ),
)


def registry_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "check_id": check.check_id,
            "category": check.category,
            "severity": check.severity,
            "schema_dependencies": list(check.schema_dependencies),
            "description": check.description,
            "introduced_in_schema_version": check.introduced_in_schema_version,
        }
        for check in CHECKS
    )
