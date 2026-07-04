"""Class/function ownership inventory for refactor gates.

This module performs static source analysis only. It does not import provider,
notification, scanner, or Event Alpha runtime modules.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import refactor_legacy_inventory
from . import refactor_v3_contract


REPORT_SCHEMA_VERSION = "refactor_class_ownership_report_v1"
REPORT_JSON = "REFACTOR_CLASS_OWNERSHIP_REPORT.json"
REPORT_MD = "REFACTOR_CLASS_OWNERSHIP_REPORT.md"
DEFAULT_CLASS_LINE_LIMIT = 75
DEFAULT_FUNCTION_LINE_LIMIT = 150

MODULE_EXCEPTIONS = {
    "crypto_rsi_scanner.event_fade": (
        "Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because "
        "TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade."
    ),
}

MODEL_BUNDLE_REASON = (
    "Small public DTO/enum/protocol/result bundle kept together as one stable import contract; "
    "all classes remain below the class-size limit."
)

ACCEPTED_MODEL_BUNDLE_MODULES = {
    "crypto_rsi_scanner.backups",
    "crypto_rsi_scanner.event_alpha.artifacts.alert_store.models",
    "crypto_rsi_scanner.event_alpha.artifacts.alerts",
    "crypto_rsi_scanner.event_alpha.artifacts.cache",
    "crypto_rsi_scanner.event_alpha.artifacts.locks",
    "crypto_rsi_scanner.event_alpha.artifacts.replay",
    "crypto_rsi_scanner.event_alpha.artifacts.research_cards.legacy_parts.models",
    "crypto_rsi_scanner.event_alpha.artifacts.retention",
    "crypto_rsi_scanner.event_alpha.artifacts.run_ledger",
    "crypto_rsi_scanner.event_alpha.config.health_guard",
    "crypto_rsi_scanner.event_alpha.config.v1_readiness",
    "crypto_rsi_scanner.event_alpha.doctor.environment",
    "crypto_rsi_scanner.event_alpha.notifications.delivery",
    "crypto_rsi_scanner.event_alpha.notifications.inbox.models",
    "crypto_rsi_scanner.event_alpha.notifications.legacy.delivery_models",
    "crypto_rsi_scanner.event_alpha.notifications.provider_status",
    "crypto_rsi_scanner.event_alpha.notifications.recipient_check",
    "crypto_rsi_scanner.event_alpha.notifications.router",
    "crypto_rsi_scanner.event_alpha.notifications.runs",
    "crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor",
    "crypto_rsi_scanner.event_alpha.outcomes.burn_in",
    "crypto_rsi_scanner.event_alpha.outcomes.feedback",
    "crypto_rsi_scanner.event_alpha.outcomes.feedback_labels",
    "crypto_rsi_scanner.event_alpha.outcomes.policy_simulator",
    "crypto_rsi_scanner.event_alpha.outcomes.priors",
    "crypto_rsi_scanner.event_alpha.outcomes.quality.models",
    "crypto_rsi_scanner.event_alpha.providers.bybit_announcements_preflight",
    "crypto_rsi_scanner.event_alpha.providers.coinalyze_preflight",
    "crypto_rsi_scanner.event_alpha.providers.dex_onchain_readiness",
    "crypto_rsi_scanner.event_alpha.providers.live_provider_readiness",
    "crypto_rsi_scanner.event_alpha.providers.official_exchange_activation",
    "crypto_rsi_scanner.event_alpha.providers.provider_health_legacy",
    "crypto_rsi_scanner.event_alpha.providers.source_registry",
    "crypto_rsi_scanner.event_alpha.providers.unlock_calendar_preflight",
    "crypto_rsi_scanner.event_alpha.radar.anomaly_state",
    "crypto_rsi_scanner.event_alpha.radar.catalyst_search.models",
    "crypto_rsi_scanner.event_alpha.radar.catalyst_search.providers",
    "crypto_rsi_scanner.event_alpha.radar.claim_semantics",
    "crypto_rsi_scanner.event_alpha.radar.core.models",
    "crypto_rsi_scanner.event_alpha.radar.core_opportunities",
    "crypto_rsi_scanner.event_alpha.radar.evidence.models",
    "crypto_rsi_scanner.event_alpha.radar.evidence_quality",
    "crypto_rsi_scanner.event_alpha.radar.graph",
    "crypto_rsi_scanner.event_alpha.radar.identity",
    "crypto_rsi_scanner.event_alpha.radar.impact_hypotheses.models",
    "crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store",
    "crypto_rsi_scanner.event_alpha.radar.impact_path_validator",
    "crypto_rsi_scanner.event_alpha.radar.incident_graph",
    "crypto_rsi_scanner.event_alpha.radar.incidents.models",
    "crypto_rsi_scanner.event_alpha.radar.llm.analyzer",
    "crypto_rsi_scanner.event_alpha.radar.llm.budget",
    "crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames",
    "crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner",
    "crypto_rsi_scanner.event_alpha.radar.llm.extraction_models",
    "crypto_rsi_scanner.event_alpha.radar.llm.extractor",
    "crypto_rsi_scanner.event_alpha.radar.llm.models",
    "crypto_rsi_scanner.event_alpha.radar.market_anomaly_scanner",
    "crypto_rsi_scanner.event_alpha.radar.market_confirmation",
    "crypto_rsi_scanner.event_alpha.radar.market_reaction",
    "crypto_rsi_scanner.event_alpha.radar.missed",
    "crypto_rsi_scanner.event_alpha.radar.near_miss.models",
    "crypto_rsi_scanner.event_alpha.radar.opportunity_verdict",
    "crypto_rsi_scanner.event_alpha.radar.pipeline",
    "crypto_rsi_scanner.event_alpha.radar.playbooks",
    "crypto_rsi_scanner.event_alpha.radar.price_history",
    "crypto_rsi_scanner.event_alpha.radar.source_coverage.models",
    "crypto_rsi_scanner.event_alpha.radar.source_enrichment",
    "crypto_rsi_scanner.event_alpha.radar.validation.models",
    "crypto_rsi_scanner.event_alpha.radar.watchlist.models",
    "crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment",
    "crypto_rsi_scanner.event_alpha.radar.watchlist_market",
    "crypto_rsi_scanner.event_alpha.shims",
    "crypto_rsi_scanner.event_core.models",
    "crypto_rsi_scanner.event_providers.base",
    "crypto_rsi_scanner.llm_providers.base",
    "crypto_rsi_scanner.llm_providers.fixture",
    "crypto_rsi_scanner.ops",
    "crypto_rsi_scanner.refactor_class_ownership_report",
    "crypto_rsi_scanner.signal_registry",
}

ACCEPTED_CLASS_EXCEPTIONS: dict[str, dict[str, str]] = {
    "crypto_rsi_scanner.client.CoinGeckoClient": {
        "class_name": "CoinGeckoClient",
        "status": "accepted_exception",
        "category": "provider_client",
        "reason": "Reusable async market-data client keeps rate-limit, retry, pagination, session, and fixture behavior in one public import contract.",
        "owner_note": "Split only with dedicated CoinGecko client parity tests; this pass intentionally avoids provider behavior churn.",
        "revisit_condition": "Revisit when adding a new CoinGecko endpoint family or changing async session/retry ownership.",
    },
    "crypto_rsi_scanner.event_alpha.radar.asset_registry.CanonicalAsset": {
        "class_name": "CanonicalAsset",
        "status": "accepted_exception",
        "category": "data_model",
        "reason": "Field-rich canonical identity value object; splitting fields from serialization would add indirection without reducing behavior risk.",
        "owner_note": "Keep schema-adjacent identity fields together while canonical resolver contracts settle.",
        "revisit_condition": "Revisit when schema v2 splits asset identity, venue symbols, and diagnostics into separate contracts.",
    },
    "crypto_rsi_scanner.event_alpha.radar.watchlist_market.CoinGeckoWatchlistMarketProvider": {
        "class_name": "CoinGeckoWatchlistMarketProvider",
        "status": "accepted_exception",
        "category": "provider_adapter",
        "reason": "Fixture/live market enrichment adapter is below file-size gates and tightly coupled to request budgeting and no-live defaults.",
        "owner_note": "Provider activation safety is more important than shaving this adapter below 75 lines.",
        "revisit_condition": "Revisit when watchlist market enrichment gains another provider implementation.",
    },
    "crypto_rsi_scanner.event_providers.binance_announcements.legacy.BinanceAnnouncementProvider": {
        "class_name": "BinanceAnnouncementProvider",
        "status": "accepted_exception",
        "category": "provider_adapter",
        "reason": "Signed/public announcement compatibility core preserves old imports and WebSocket/fixture behavior.",
        "owner_note": "Do not split further without signed-listener fixture parity and secret-redaction tests.",
        "revisit_condition": "Revisit when Binance public rehearsal becomes a first-class activated provider path.",
    },
    "crypto_rsi_scanner.event_providers.bybit_announcements.legacy.BybitAnnouncementProvider": {
        "class_name": "BybitAnnouncementProvider",
        "status": "accepted_exception",
        "category": "provider_adapter",
        "reason": "Small HTTP announcement adapter is only slightly over the advisory class limit and already package-scoped.",
        "owner_note": "Avoid touching Bybit request/normalization behavior outside provider-activation work.",
        "revisit_condition": "Revisit when adding another Bybit announcement endpoint or response shape.",
    },
    "crypto_rsi_scanner.event_providers.cryptopanic.legacy.CryptoPanicProvider": {
        "class_name": "CryptoPanicProvider",
        "status": "accepted_exception",
        "category": "provider_adapter",
        "reason": "Compatibility class still owns request hygiene, token redaction, quota/ledger telemetry, parser normalization, and fixture/live no-call behavior.",
        "owner_note": "The package already has client/parser/request_ledger homes; moving the remaining class body should be its own provider parity pass.",
        "revisit_condition": "Revisit when CryptoPanic live activation or request-ledger semantics change.",
    },
    "crypto_rsi_scanner.event_providers.gdelt.GdeltProvider": {
        "class_name": "GdeltProvider",
        "status": "accepted_exception",
        "category": "provider_adapter",
        "reason": "No-key public provider is fail-soft and only slightly over the advisory limit.",
        "owner_note": "Keep current timeout/429 behavior stable; public-provider noise is expected.",
        "revisit_condition": "Revisit when adding a second GDELT mode or durable request ledger.",
    },
    "crypto_rsi_scanner.event_providers.prediction_market_events.PredictionMarketEventsProvider": {
        "class_name": "PredictionMarketEventsProvider",
        "status": "accepted_exception",
        "category": "provider_adapter",
        "reason": "Small no-key prediction-market provider keeps fixture/live parsing in one stable adapter.",
        "owner_note": "Split only when another prediction-market provider is added.",
        "revisit_condition": "Revisit when Polymarket Gamma support grows beyond the current parser.",
    },
    "crypto_rsi_scanner.event_providers.project_blog_rss.ProjectBlogRssProvider": {
        "class_name": "ProjectBlogRssProvider",
        "status": "accepted_exception",
        "category": "provider_adapter",
        "reason": "RSS/Atom adapter is tightly coupled to per-feed fail-soft behavior and source normalization.",
        "owner_note": "Keep feed failure semantics stable unless adding a reusable RSS client layer.",
        "revisit_condition": "Revisit when project-blog sources get persistent request ledgers or richer feed classes.",
    },
    "crypto_rsi_scanner.llm_providers.openai_provider.OpenAILLMRelationshipProvider": {
        "class_name": "OpenAILLMRelationshipProvider",
        "status": "accepted_exception",
        "category": "llm_provider",
        "reason": "OpenAI relationship provider keeps request assembly, timeout/error handling, and structured parsing together behind explicit opt-in gates.",
        "owner_note": "Do not alter LLM provider behavior during a refactor-only pass.",
        "revisit_condition": "Revisit when adding a second live LLM backend or shared OpenAI transport abstraction.",
    },
    "crypto_rsi_scanner.llm_providers.openai_provider.OpenAILLMExtractionProvider": {
        "class_name": "OpenAILLMExtractionProvider",
        "status": "accepted_exception",
        "category": "llm_provider",
        "reason": "Small extraction provider is barely over the advisory threshold and shares safety semantics with the relationship provider.",
        "owner_note": "Keep quote-validation and no-live defaults stable.",
        "revisit_condition": "Revisit with a broader OpenAI provider transport split.",
    },
    "crypto_rsi_scanner.storage_parts.migrations.MigrationsMixin": {
        "class_name": "MigrationsMixin",
        "status": "accepted_exception",
        "category": "storage_mixin",
        "reason": "SQLite migration ownership is intentionally centralized to avoid untested schema drift.",
        "owner_note": "DB schema behavior must not change in this cleanup pass.",
        "revisit_condition": "Revisit only with explicit migration tests and backup/restore verification.",
    },
    "crypto_rsi_scanner.storage_parts.signals.SignalsMixin": {
        "class_name": "SignalsMixin",
        "status": "accepted_exception",
        "category": "storage_mixin",
        "reason": "Signal persistence methods share schema assumptions, row serialization, and outcome lookup behavior.",
        "owner_note": "Avoid splitting storage write paths without SQLite roundtrip parity tests.",
        "revisit_condition": "Revisit when storage schema v2 or a repository layer is introduced.",
    },
    "crypto_rsi_scanner.storage_parts.watchlist.WatchlistMixin": {
        "class_name": "WatchlistMixin",
        "status": "accepted_exception",
        "category": "storage_mixin",
        "reason": "Watchlist persistence methods are stable DB helpers and only slightly exceed the advisory limit.",
        "owner_note": "No DB schema or paper/watchlist behavior changes in this refactor pass.",
        "revisit_condition": "Revisit when watchlist storage grows new tables or migrations.",
    },
}

PROVIDER_CLASS_SPLIT_TARGETS = {
    "CryptoPanicProvider",
    "BinanceAnnouncementProvider",
    "BybitAnnouncementProvider",
    "CoinalyzeDerivativesProvider",
    "GdeltProvider",
    "PredictionMarketEventsProvider",
    "ProjectBlogRssProvider",
    "CoinGeckoWatchlistMarketProvider",
    "OpenAILLMRelationshipProvider",
    "OpenAILLMExtractionProvider",
}

STORAGE_MIXIN_CLASSES = {"SignalsMixin", "WatchlistMixin", "MigrationsMixin"}

NEAR_THRESHOLD_LINE_FLOOR = 1300


@dataclass(frozen=True)
class ClassOwnershipRow:
    module: str
    class_name: str
    qualname: str
    line_count: int
    public: bool
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FunctionOwnershipRow:
    module: str
    function_name: str
    qualname: str
    line_count: int
    public: bool
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def _class_exception_key(row: ClassOwnershipRow | Mapping[str, Any]) -> str:
    module = str(row.module if isinstance(row, ClassOwnershipRow) else row.get("module") or "")
    qualname = str(row.qualname if isinstance(row, ClassOwnershipRow) else row.get("qualname") or "")
    return f"{module}.{qualname}"


def _class_exception_for_row(row: ClassOwnershipRow) -> dict[str, str] | None:
    return ACCEPTED_CLASS_EXCEPTIONS.get(_class_exception_key(row))


def _class_row_with_exception(row: ClassOwnershipRow) -> dict[str, Any]:
    class_exception = _class_exception_for_row(row)
    module_exception = MODULE_EXCEPTIONS.get(row.module)
    payload = row.to_dict()
    payload.update(
        {
            "exception_reason": (class_exception or {}).get("reason") or module_exception,
            "accepted_exception": bool(class_exception),
            "exception_status": (class_exception or {}).get("status") or "",
            "exception_category": (class_exception or {}).get("category") or "",
            "owner_note": (class_exception or {}).get("owner_note") or "",
            "revisit_condition": (class_exception or {}).get("revisit_condition") or "",
        }
    )
    return payload


def build_report(
    *,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
    class_line_limit: int = DEFAULT_CLASS_LINE_LIMIT,
    function_line_limit: int = DEFAULT_FUNCTION_LINE_LIMIT,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    package_root = repo_root / "crypto_rsi_scanner"
    classes, functions = _collect_source_rows(package_root, repo_root=repo_root)
    public_classes = [row for row in classes if row.public]
    classes_by_module = Counter(row.module for row in public_classes)
    multi_public_class_modules = _multi_public_class_module_rows(public_classes, classes_by_module)
    accepted_model_bundles = [
        row for row in multi_public_class_modules if row.get("resolution") == "accepted_model_bundle"
    ]
    unresolved_multi_class_modules = [
        row for row in multi_public_class_modules if row.get("resolution") == "unresolved"
    ]
    long_classes = [
        _class_row_with_exception(row)
        for row in classes
        if row.line_count > class_line_limit
    ]
    accepted_class_exceptions = [row for row in long_classes if row.get("accepted_exception")]
    remaining_class_debt = [row for row in long_classes if not row.get("accepted_exception")]
    long_functions = [
        row.to_dict()
        for row in functions
        if row.line_count > function_line_limit
    ]
    exception_rows = [
        {
            "module": module,
            "reason": reason,
            "public_class_count": classes_by_module.get(module, 0),
        }
        for module, reason in sorted(MODULE_EXCEPTIONS.items())
    ]
    legacy_inventory = refactor_legacy_inventory.build_legacy_inventory(
        root=repo_root,
        class_line_limit=class_line_limit,
        function_line_limit=function_line_limit,
    )
    v3_gate_snapshot = refactor_v3_contract.build_v3_gate_snapshot(
        root=repo_root,
        shim_dependency_report=_shim_dependency_report_snapshot(repo_root),
        class_ownership_report={
            "modules_with_multiple_public_classes": unresolved_multi_class_modules,
            "unresolved_multi_class_modules": unresolved_multi_class_modules,
            "accepted_class_exceptions_count": len(accepted_class_exceptions),
            "functions_over_limit_count": len(long_functions),
        },
    )
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "refactor_class_ownership_report",
        "generated_at": generated,
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        "class_line_limit": class_line_limit,
        "function_line_limit": function_line_limit,
        "public_class_count": len(public_classes),
        "class_count": len(classes),
        "function_count": len(functions),
        "classes_over_limit_count": len(long_classes),
        "functions_over_limit_count": len(long_functions),
        "production_classes_over_limit": len(long_classes),
        "production_functions_over_limit": len(long_functions),
        "production_classes_over_limit_rows": long_classes,
        "production_functions_over_limit_rows": long_functions,
        "accepted_class_exceptions": accepted_class_exceptions,
        "accepted_class_exceptions_count": len(accepted_class_exceptions),
        "remaining_class_ownership_debt": remaining_class_debt,
        "remaining_class_ownership_debt_count": len(remaining_class_debt),
        "v3_gate_status": v3_gate_snapshot["status"],
        "v3_auto_accept_ready": v3_gate_snapshot["v3_auto_accept_ready"],
        "v3_gates": v3_gate_snapshot["gate_values"],
        "v3_gate_snapshot": v3_gate_snapshot,
        "public_classes_not_in_own_module": v3_gate_snapshot["gate_values"]["public_classes_not_in_own_module"],
        "class_exceptions_remaining": v3_gate_snapshot["gate_values"]["class_exceptions_remaining"],
        "functions_over_150_lines": v3_gate_snapshot["gate_values"]["functions_over_150_lines"],
        "provider_class_split_status": _provider_class_split_status(classes, long_classes),
        "storage_mixin_exception_status": _storage_mixin_exception_status(classes, long_classes),
        "near_threshold_file_status": _near_threshold_file_status(package_root, repo_root=repo_root),
        "near_threshold_file_status_floor": NEAR_THRESHOLD_LINE_FLOOR,
        "modules_with_multiple_public_classes_status": (
            "pass" if not unresolved_multi_class_modules else "blocked_unregistered_modules"
        ),
        "modules_with_multiple_public_classes_revisit_condition": (
            "Register tiny model bundles explicitly or split behaviorful public classes before adding "
            "new multi-class production modules."
        ),
        "modules_with_multiple_public_classes_count": len(unresolved_multi_class_modules),
        "multi_public_class_modules_count": len(multi_public_class_modules),
        "accepted_model_bundles_count": len(accepted_model_bundles),
        "unresolved_multi_class_modules_count": len(unresolved_multi_class_modules),
        "public_classes_by_module": dict(sorted(classes_by_module.items())),
        "classes_over_limit": long_classes,
        "functions_over_limit": long_functions,
        "multi_public_class_modules": multi_public_class_modules,
        "accepted_model_bundles": accepted_model_bundles,
        "unresolved_multi_class_modules": unresolved_multi_class_modules,
        "modules_with_multiple_public_classes": unresolved_multi_class_modules,
        "legacy_files_over_1500_lines": legacy_inventory["legacy_files_over_1500_lines"],
        "legacy_files_over_3000_lines": legacy_inventory["legacy_files_over_3000_lines"],
        "legacy_total_lines": legacy_inventory["legacy_total_lines"],
        "largest_legacy_files": legacy_inventory["largest_legacy_files"],
        "legacy_classes_over_limit": legacy_inventory["legacy_classes_over_limit"],
        "legacy_functions_over_limit": legacy_inventory["legacy_functions_over_limit"],
        "legacy_modules_with_multiple_public_classes": legacy_inventory[
            "legacy_modules_with_multiple_public_classes"
        ],
        "legacy_classes_over_limit_rows": legacy_inventory["legacy_classes_over_limit_rows"],
        "legacy_functions_over_limit_rows": legacy_inventory["legacy_functions_over_limit_rows"],
        "legacy_modules_with_multiple_public_classes_rows": legacy_inventory[
            "legacy_modules_with_multiple_public_classes_rows"
        ],
        "legacy_decomposition_gate_status": legacy_inventory["legacy_decomposition_gate_status"],
        "exceptions": exception_rows,
        "policy": {
            "public_class_over_75_lines": "should live in its own module unless documented here",
            "multiple_public_classes": (
                "blocker unless the module is registered as an accepted model bundle or module exception"
            ),
            "internal_helper_class_over_75_lines": "should be split or documented",
            "new_multi_public_class_module": "fails refactor gates unless registered as a model bundle",
        },
    }


def _provider_class_split_status(
    classes: Iterable[ClassOwnershipRow],
    long_classes: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    long_by_key = {_class_exception_key(row): dict(row) for row in long_classes}
    rows: list[dict[str, Any]] = []
    for row in classes:
        if row.class_name not in PROVIDER_CLASS_SPLIT_TARGETS:
            continue
        key = _class_exception_key(row)
        exception = ACCEPTED_CLASS_EXCEPTIONS.get(key)
        over_limit = row.line_count > DEFAULT_CLASS_LINE_LIMIT
        rows.append(
            {
                "class_name": row.class_name,
                "module": row.module,
                "source_path": row.source_path,
                "line_count": row.line_count,
                "over_limit": over_limit,
                "split_status": (
                    (exception or {}).get("status")
                    if over_limit and exception
                    else "below_threshold"
                    if not over_limit
                    else "needs_split_or_exception"
                ),
                "reason": (exception or {}).get("reason") or "",
                "owner_note": (exception or {}).get("owner_note") or "",
                "revisit_condition": (exception or {}).get("revisit_condition") or "",
                "accepted_exception": bool(long_by_key.get(key, {}).get("accepted_exception")),
            }
        )
    return sorted(rows, key=lambda item: (str(item["class_name"]), str(item["module"])))


def _multi_public_class_module_rows(
    public_classes: Iterable[ClassOwnershipRow],
    classes_by_module: Counter[str],
) -> list[dict[str, Any]]:
    class_rows_by_module: dict[str, list[ClassOwnershipRow]] = {}
    for row in public_classes:
        class_rows_by_module.setdefault(row.module, []).append(row)

    rows: list[dict[str, Any]] = []
    for module, count in sorted(classes_by_module.items()):
        if count <= 1:
            continue
        module_classes = sorted(class_rows_by_module.get(module, []), key=lambda row: row.qualname)
        class_names = [row.qualname for row in module_classes]
        max_line_count = max((row.line_count for row in module_classes), default=0)
        model_bundle_reason = MODEL_BUNDLE_REASON if module in ACCEPTED_MODEL_BUNDLE_MODULES else ""
        exception_reason = MODULE_EXCEPTIONS.get(module) or ""
        accepted_model_bundle = bool(model_bundle_reason)
        rows.append(
            {
                "module": module,
                "public_class_count": count,
                "class_names": class_names,
                "max_class_line_count": max_line_count,
                "accepted": accepted_model_bundle,
                "accepted_model_bundle": accepted_model_bundle,
                "model_bundle_reason": model_bundle_reason,
                "reason": model_bundle_reason or exception_reason,
                "exception_reason": exception_reason,
                "resolution": (
                    "accepted_model_bundle"
                    if accepted_model_bundle
                    else "module_exception"
                    if exception_reason
                    else "unresolved"
                ),
            }
        )
    return rows


def _shim_dependency_report_snapshot(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "research" / "EVENT_ALPHA_SHIM_DEPENDENCY_REPORT.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            return data
    return {
        "entries": [],
        "internal_import_reference_count": 0,
        "docs_reference_count": 0,
        "artifact_doc_reference_count": 0,
        "removal_candidate_counts": {},
    }


def _storage_mixin_exception_status(
    classes: Iterable[ClassOwnershipRow],
    long_classes: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    long_by_key = {_class_exception_key(row): dict(row) for row in long_classes}
    rows: list[dict[str, Any]] = []
    for row in classes:
        if row.class_name not in STORAGE_MIXIN_CLASSES:
            continue
        key = _class_exception_key(row)
        exception = ACCEPTED_CLASS_EXCEPTIONS.get(key)
        rows.append(
            {
                "class_name": row.class_name,
                "module": row.module,
                "source_path": row.source_path,
                "line_count": row.line_count,
                "over_limit": row.line_count > DEFAULT_CLASS_LINE_LIMIT,
                "exception_status": (exception or {}).get("status") or "",
                "reason": (exception or {}).get("reason") or "",
                "owner_note": (exception or {}).get("owner_note") or "",
                "revisit_condition": (exception or {}).get("revisit_condition") or "",
                "accepted_exception": bool(long_by_key.get(key, {}).get("accepted_exception")),
            }
        )
    return sorted(rows, key=lambda item: str(item["class_name"]))


def _near_threshold_file_status(package_root: Path, *, repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            line_count = sum(1 for _line in path.open(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if line_count < NEAR_THRESHOLD_LINE_FLOOR or line_count > 1500:
            continue
        rel = path.relative_to(repo_root).as_posix()
        rows.append(
            {
                "path": rel,
                "line_count": line_count,
                "status": "accepted_near_threshold",
                "reason": "Below the production warning threshold; split only when making related behavior-preserving changes.",
                "revisit_condition": "Revisit if the file crosses 1,500 lines or gains a new large class/function violation.",
            }
        )
    return sorted(rows, key=lambda row: (-int(row["line_count"]), str(row["path"])))[:40]


def write_report(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    report = build_report(root=repo_root, generated_at=generated_at)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_report(report), encoding="utf-8")
    return json_path, md_path, report


def format_report(report: dict[str, Any]) -> str:
    lines = [
        "# Refactor Class Ownership Report",
        "",
        "Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- public_class_count: `{report.get('public_class_count', 0)}`",
        f"- classes_over_limit_count: `{report.get('classes_over_limit_count', 0)}`",
        f"- functions_over_limit_count: `{report.get('functions_over_limit_count', 0)}`",
        f"- production_classes_over_limit: `{report.get('production_classes_over_limit', 0)}`",
        f"- production_functions_over_limit: `{report.get('production_functions_over_limit', 0)}`",
        f"- accepted_class_exceptions_count: `{report.get('accepted_class_exceptions_count', 0)}`",
        f"- remaining_class_ownership_debt_count: `{report.get('remaining_class_ownership_debt_count', 0)}`",
        f"- v3_gate_status: `{report.get('v3_gate_status')}`",
        f"- v3_auto_accept_ready: `{report.get('v3_auto_accept_ready')}`",
        f"- public_classes_not_in_own_module: `{report.get('public_classes_not_in_own_module', 0)}`",
        f"- class_exceptions_remaining: `{report.get('class_exceptions_remaining', 0)}`",
        f"- functions_over_150_lines: `{report.get('functions_over_150_lines', 0)}`",
        f"- modules_with_multiple_public_classes_count: `{report.get('modules_with_multiple_public_classes_count', 0)}`",
        f"- modules_with_multiple_public_classes_status: `{report.get('modules_with_multiple_public_classes_status')}`",
        f"- multi_public_class_modules_count: `{report.get('multi_public_class_modules_count', 0)}`",
        f"- accepted_model_bundles_count: `{report.get('accepted_model_bundles_count', 0)}`",
        f"- unresolved_multi_class_modules_count: `{report.get('unresolved_multi_class_modules_count', 0)}`",
        f"- legacy_decomposition_gate_status: `{report.get('legacy_decomposition_gate_status')}`",
        f"- legacy_classes_over_limit: `{report.get('legacy_classes_over_limit', 0)}`",
        f"- legacy_functions_over_limit: `{report.get('legacy_functions_over_limit', 0)}`",
        f"- legacy_modules_with_multiple_public_classes: `{report.get('legacy_modules_with_multiple_public_classes', 0)}`",
        "",
        "## Policy",
        "",
        "- Every public class over 75 lines should live in its own module unless documented as an exception.",
        "- Multiple tiny value objects/enums/protocol DTOs may live together only when registered as accepted model bundles.",
        "- Internal helper classes over 75 lines should also be split or documented.",
        "- Refactor v3 expects public classes to live in their own modules unless the module is a documented model bundle.",
        "- Refactor v3 keeps accepted class exceptions pending until each exception is reaccepted for the v3 removal phase.",
        "- `event_fade.py` remains outside Event Alpha; Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts but must not create `TRIGGERED_FADE`.",
        "",
    ]
    _append_v3_class_gate_section(lines, report)
    lines.extend(
        [
        "## Exceptions",
        "",
        ]
    )
    for row in report.get("exceptions", []):
        if isinstance(row, dict):
            lines.append(f"- `{row.get('module')}`: {row.get('reason')}")
    lines.extend([
        "",
        "## Accepted Class Exceptions",
        "",
        "| module | class | lines | category | owner note | revisit condition |",
        "|---|---|---:|---|---|---|",
    ])
    accepted_rows = list(_limit_rows(report.get("accepted_class_exceptions"), 80))
    if accepted_rows:
        for row in accepted_rows:
            lines.append(
                f"| `{row.get('module')}` | `{row.get('qualname')}` | {row.get('line_count', 0)} | "
                f"{row.get('exception_category') or ''} | {row.get('owner_note') or ''} | "
                f"{row.get('revisit_condition') or ''} |"
            )
    else:
        lines.append("| none | none | 0 | none | none | none |")
    lines.extend([
        "",
        "## Provider Class Split Status",
        "",
        "| class | module | lines | status | revisit condition |",
        "|---|---|---:|---|---|",
    ])
    for row in _limit_rows(report.get("provider_class_split_status"), 80):
        lines.append(
            f"| `{row.get('class_name')}` | `{row.get('module')}` | {row.get('line_count', 0)} | "
            f"{row.get('split_status') or row.get('exception_status') or ''} | "
            f"{row.get('revisit_condition') or ''} |"
        )
    lines.extend([
        "",
        "## Storage Mixin Exceptions",
        "",
        "| class | module | lines | status | revisit condition |",
        "|---|---|---:|---|---|",
    ])
    for row in _limit_rows(report.get("storage_mixin_exception_status"), 40):
        lines.append(
            f"| `{row.get('class_name')}` | `{row.get('module')}` | {row.get('line_count', 0)} | "
            f"{row.get('exception_status') or ''} | {row.get('revisit_condition') or ''} |"
        )
    lines.extend([
        "",
        "## Near-Threshold Production Files",
        "",
        "| path | lines | status | revisit condition |",
        "|---|---:|---|---|",
    ])
    for row in _limit_rows(report.get("near_threshold_file_status"), 40):
        lines.append(
            f"| `{row.get('path')}` | {row.get('line_count', 0)} | {row.get('status') or ''} | "
            f"{row.get('revisit_condition') or ''} |"
        )
    lines.extend([
        "",
        "## Legacy Implementation Cores",
        "",
        "| path | lines |",
        "|---|---:|",
    ])
    for row in _limit_rows(report.get("largest_legacy_files"), 40):
        lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    _append_multi_class_sections(lines, report)
    lines.extend([
        "",
        "## Classes Over 75 Lines",
        "",
        "| module | class | lines | public | accepted | exception |",
        "|---|---|---:|---:|---:|---|",
    ])
    for row in _limit_rows(report.get("classes_over_limit"), 80):
        lines.append(
            f"| `{row.get('module')}` | `{row.get('qualname')}` | {row.get('line_count', 0)} | "
            f"{str(bool(row.get('public'))).lower()} | "
            f"{str(bool(row.get('accepted_exception'))).lower()} | {row.get('exception_reason') or ''} |"
        )
    lines.extend([
        "",
        "## Functions Over 150 Lines",
        "",
        "| module | function | lines | public |",
        "|---|---|---:|---:|",
    ])
    for row in _limit_rows(report.get("functions_over_limit"), 120):
        lines.append(
            f"| `{row.get('module')}` | `{row.get('qualname')}` | {row.get('line_count', 0)} | "
            f"{str(bool(row.get('public'))).lower()} |"
    )
    return "\n".join(lines).rstrip() + "\n"


def _append_multi_class_sections(lines: list[str], report: dict[str, Any]) -> None:
    lines.extend([
        "",
        "## Accepted Model Bundles",
        "",
        "| module | classes | max class lines | accepted | reason |",
        "|---|---:|---:|---:|---|",
    ])
    for row in _limit_rows(report.get("accepted_model_bundles"), 120):
        lines.append(
            f"| `{row.get('module')}` | {row.get('public_class_count', 0)} | "
            f"{row.get('max_class_line_count', 0)} | {str(bool(row.get('accepted'))).lower()} | "
            f"{row.get('reason') or ''} |"
        )
    lines.extend([
        "",
        "## Unresolved Multi-Class Modules",
        "",
        "| module | public classes | max class lines | reason |",
        "|---|---:|---:|---|",
    ])
    unresolved_rows = list(_limit_rows(report.get("unresolved_multi_class_modules"), 120))
    if unresolved_rows:
        for row in unresolved_rows:
            lines.append(
                f"| `{row.get('module')}` | {row.get('public_class_count', 0)} | "
                f"{row.get('max_class_line_count', 0)} | {row.get('reason') or ''} |"
            )
    else:
        lines.append("| none | 0 | 0 | all current multi-class modules are registered or explicitly excepted |")
    lines.extend([
        "",
        "## Multi-Public-Class Module Inventory",
        "",
        "| module | public classes | max class lines | resolution | reason |",
        "|---|---:|---:|---|---|",
    ])
    for row in _limit_rows(report.get("multi_public_class_modules"), 120):
        lines.append(
            f"| `{row.get('module')}` | {row.get('public_class_count', 0)} | "
            f"{row.get('max_class_line_count', 0)} | {row.get('resolution') or ''} | "
            f"{row.get('reason') or ''} |"
        )


def _append_v3_class_gate_section(lines: list[str], report: dict[str, Any]) -> None:
    lines.extend(
        [
            "## Refactor V3 Gates",
            "",
            "| gate | value | severity |",
            "|---|---:|---|",
        ]
    )
    v3_snapshot = report.get("v3_gate_snapshot") if isinstance(report.get("v3_gate_snapshot"), dict) else {}
    v3_values = v3_snapshot.get("gate_values") if isinstance(v3_snapshot.get("gate_values"), dict) else {}
    v3_severity = v3_snapshot.get("gate_severity") if isinstance(v3_snapshot.get("gate_severity"), dict) else {}
    for name in refactor_v3_contract.V3_GATE_NAMES:
        lines.append(f"| `{name}` | {v3_values.get(name, 0)} | {v3_severity.get(name, '')} |")
    lines.append("")


def _collect_source_rows(package_root: Path, *, repo_root: Path) -> tuple[list[ClassOwnershipRow], list[FunctionOwnershipRow]]:
    classes: list[ClassOwnershipRow] = []
    functions: list[FunctionOwnershipRow] = []
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = _module_name(path, repo_root=repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=path.as_posix())
        except SyntaxError:
            continue
        visitor = _OwnershipVisitor(module, path.relative_to(repo_root).as_posix())
        visitor.visit(tree)
        classes.extend(visitor.classes)
        functions.extend(visitor.functions)
    return classes, functions


class _OwnershipVisitor(ast.NodeVisitor):
    def __init__(self, module: str, source_path: str) -> None:
        self.module = module
        self.source_path = source_path
        self.stack: list[str] = []
        self.classes: list[ClassOwnershipRow] = []
        self.functions: list[FunctionOwnershipRow] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = ".".join((*self.stack, node.name)) if self.stack else node.name
        self.classes.append(
            ClassOwnershipRow(
                module=self.module,
                class_name=node.name,
                qualname=qualname,
                line_count=_node_lines(node),
                public=not node.name.startswith("_"),
                source_path=self.source_path,
            )
        )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualname = ".".join((*self.stack, node.name)) if self.stack else node.name
        self.functions.append(
            FunctionOwnershipRow(
                module=self.module,
                function_name=node.name,
                qualname=qualname,
                line_count=_node_lines(node),
                public=not node.name.startswith("_"),
                source_path=self.source_path,
            )
        )


def _node_lines(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    start = getattr(node, "lineno", None)
    if not isinstance(end, int) or not isinstance(start, int):
        return 0
    return max(0, end - start + 1)


def _module_name(path: Path, *, repo_root: Path) -> str:
    rel = path.relative_to(repo_root).with_suffix("")
    return ".".join(rel.parts)


def _limit_rows(rows: object, limit: int) -> Iterable[dict[str, Any]]:
    if not isinstance(rows, list):
        return ()
    return (row for row in rows[:limit] if isinstance(row, dict))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write refactor class/function ownership report artifacts.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)
    json_path, md_path, report = write_report(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    print(f"classes_over_limit_count={report.get('classes_over_limit_count', 0)}")
    print(f"functions_over_limit_count={report.get('functions_over_limit_count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
