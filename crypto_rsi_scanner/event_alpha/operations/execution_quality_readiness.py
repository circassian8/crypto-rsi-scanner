"""Static, no-network execution-quality selection and readiness contract.

The owner selected Bybit USDT-linear perpetuals with public market data only.
This report records that choice and the separately gated public REST adapter
while stopping before provider authorization or live activation.  It reads no
environment, credentials, files, provider state, or holdout data and performs
no writes or network calls.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from typing import Mapping, Protocol, Sequence


CONTRACT_VERSION = "crypto_radar_execution_quality_readiness_v10"
EXECUTION_MODES = ("spot", "perpetual", "dex")
OFFICIAL_PUBLIC_FEE_REFERENCE_URL = (
    "https://www.bybit.com/en/help-center/article/Trading-Fee-Structure"
)
OFFICIAL_ACCOUNT_FEE_RATE_ENDPOINT_DOC_URL = (
    "https://bybit-exchange.github.io/docs/v5/account/fee-rate"
)
REMAINING_PROTOCOL_V2_COST_FIELDS = (
    "fee_rate_source_and_assumption",
    "entry_exit_order_style",
    "notional_tiers_usdt",
    "spread_and_visible_book_impact_application",
    "slippage_beyond_visible_book_policy",
    "funding_holding_period_and_sign_treatment",
    "latency_cost_policy",
    "unavailable_cost_policy",
)
REMAINING_PROTOCOL_V2_SEALING_FIELDS = (
    "exact_frozen_eligible_instrument_set",
    *REMAINING_PROTOCOL_V2_COST_FIELDS,
    "protocol_v2_final_annex",
)
_MODE_ACCESS = {
    "spot": (
        "public_order_book_reads_expected_without_credentials",
        "operator_must_confirm_venue_and_account_eligibility; no_trading_authorization_requested",
    ),
    "perpetual": (
        "public_order_book_reads_expected_without_credentials",
        "operator_must_confirm_derivatives_jurisdiction_and_account_eligibility; no_trading_authorization_requested",
    ),
    "dex": (
        "RPC_or_quote_access_and_credentials_unknown_until_chain_and_provider_selection",
        "operator_must_select_chain_tokens_pool_or_router_and_network; no_wallet_or_order_authorization_requested",
    ),
}
COMMON_METRICS = (
    "best_bid",
    "best_ask",
    "mid_price",
    "spread_bps",
    "bid_depth_usd_by_band",
    "ask_depth_usd_by_band",
    "buy_price_impact_bps_by_notional",
    "sell_price_impact_bps_by_notional",
    "provider_observed_at",
    "acquired_at",
    "freshness_status",
)
BYBIT_NATIVE_METRICS = (
    "best_bid",
    "best_ask",
    "mid_price",
    "spread_bps",
    "bid_depth_usdt_by_band",
    "ask_depth_usdt_by_band",
    "buy_price_impact_bps_by_notional_usdt",
    "sell_price_impact_bps_by_notional_usdt",
    "notional_currency",
    "provider_observed_at",
    "snapshot_generated_at",
    "acquired_at",
    "age_seconds",
    "freshness_status",
    "order_book_update_id",
    "order_book_cross_sequence",
    "impact_reference",
    "impact_method",
    "impact_size_definition",
    "liquidity_scope",
    "rpi_orders_included",
)
REQUIRED_SNAPSHOT_FIELDS = (
    "schema_version",
    "venue_id",
    "execution_mode",
    "instrument_id",
    "canonical_asset_id",
    "base_asset",
    "quote_asset",
    "provider_observed_at",
    "acquired_at",
    "freshness_status",
    "best_bid",
    "best_ask",
    "mid_price",
    "spread_bps",
    "bid_depth_usd_by_band",
    "ask_depth_usd_by_band",
    "buy_price_impact_bps_by_notional",
    "sell_price_impact_bps_by_notional",
    "source_url",
    "request_lineage_id",
    "research_only",
)
MULTI_VENUE_RESEARCH_OPTION = {
    "mode_id": "multiple_venue_research",
    "status": "feasible_research_only_not_implemented",
    "execution_mode": "none_comparative_read_only_research",
    "quote_currency_policy": (
        "preserve_each_native_quote_and_normalize_only_after_the_operator_seals_"
        "a_reference_quote"
    ),
    "market_data_access": (
        "separate_public_order_book_reads_expected_without_credentials_for_each_"
        "selected_cex;DEX_access_remains_provider_specific"
    ),
    "credentials_required": "none_for_expected_cex_public_books",
    "quality_fields": (
        "per_venue_best_bid_ask_spread_depth_and_price_impact;never_blend_away_"
        "venue_identity_or_missing_depth"
    ),
    "instrument_mapping": (
        "exact_cross_venue_base_quote_contract_and_instrument_identity_required"
    ),
    "jurisdiction_and_limits": (
        "eligibility_and_request_budgets_must_be_confirmed_independently_for_every_"
        "included_venue"
    ),
    "protocol_v2_suitability": (
        "useful_for_venue_robustness_research_but_cannot_close_the_primary_cost_"
        "model_until_one_execution_surface_is_sealed"
    ),
    "security_boundary": (
        "no_credentials_orders_wallets_or_trading_permission;each_future_read_"
        "provider_requires_its_own_review_and_authorization_boundary"
    ),
    "operator_decision": (
        "choose_exact_venues_instruments_reference_quote_and_primary_execution_"
        "surface_or_reject_multi_venue_mode"
    ),
}


@dataclass(frozen=True)
class _ExecutionVenueCapability:
    """One static candidate capability; feasibility is not authorization."""

    venue_id: str
    display_name: str
    implementation_status: str
    execution_modes: tuple[str, ...]
    market_data_access: str
    public_endpoint_expected: bool | None
    credentials_required: tuple[str, ...]
    required_operator_inputs: tuple[str, ...]
    jurisdiction_constraints: tuple[str, ...]
    network_constraints: tuple[str, ...]
    request_limits: tuple[str, ...]
    expected_metrics: tuple[str, ...]
    official_source_urls: tuple[str, ...]
    official_sources_reviewed_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class _ExecutionQualityRequest:
    """Venue-specific read request prepared only after an operator decision."""

    venue_id: str
    execution_mode: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str | None
    depth_bands_bps: tuple[int, ...]
    notionals_usd: tuple[float, ...]
    chain_id: str | None = None
    pool_or_router_id: str | None = None


@dataclass(frozen=True)
class _ExecutionQualitySnapshot:
    """Closed normalized result expected from a future read-only adapter."""

    schema_version: str
    venue_id: str
    execution_mode: str
    instrument_id: str
    canonical_asset_id: str
    base_asset: str
    quote_asset: str | None
    provider_observed_at: str
    acquired_at: str
    freshness_status: str
    best_bid: float
    best_ask: float
    mid_price: float
    spread_bps: float
    bid_depth_usd_by_band: Mapping[int, float]
    ask_depth_usd_by_band: Mapping[int, float]
    buy_price_impact_bps_by_notional: Mapping[float, float]
    sell_price_impact_bps_by_notional: Mapping[float, float]
    source_url: str
    request_lineage_id: str
    research_only: bool = True
    chain_id: str | None = None
    block_number: int | None = None
    pool_or_router_id: str | None = None
    gas_estimate_native: float | None = None
    route_identity: str | None = None


class _ExecutionQualityReader(Protocol):
    """Read-only future adapter boundary; intentionally has no order methods."""

    venue_id: str

    def read_execution_quality(
        self, request: ExecutionQualityRequest
    ) -> ExecutionQualitySnapshot: ...


@dataclass(frozen=True)
class _ExecutionQualityReadiness:
    """Static operator-facing readiness result."""

    contract_version: str
    status: str
    selected_venue: str | None
    selected_execution_mode: str | None
    intended_venue: str | None
    intended_instrument_mode: str | None
    quote_currency: str | None
    primary_cost_currency: str | None
    primary_cost_currency_policy: str
    primary_cost_currency_policy_sealed: bool
    usd_equivalence_assumed: bool
    protocol_v2_cost_model_sealed: bool
    remaining_protocol_v2_cost_fields: tuple[str, ...]
    fee_rate_authority_status: str
    public_fee_reference_url: str
    account_fee_rate_endpoint_doc_url: str
    account_fee_endpoint_requires_credentials: bool
    account_specific_fee_rate_access_authorized: bool
    official_fee_sources_reviewed_at: str
    eligible_instrument_set: tuple[str, ...]
    eligible_instrument_selection_rule: str | None
    eligible_instrument_set_frozen: bool
    jurisdiction_and_account_eligibility_confirmation: str | None
    jurisdiction_and_account_eligibility_confirmed: bool | None
    expected_public_private_data_boundary: str | None
    human_decision_confirmed_at: str | None
    required_human_decision_fields: tuple[str, ...]
    human_decision_template: tuple[tuple[str, str], ...]
    supported_offline_adapters: tuple[str, ...]
    supported_live_adapters: tuple[str, ...]
    supported_evidence_stores: tuple[str, ...]
    immutable_capture_contract_implemented: bool
    protocol_v2_annex_bound: bool
    protocol_v2_evidence_eligible: bool
    supported_interface_modes: tuple[str, ...]
    feasible_venues: tuple[ExecutionVenueCapability, ...]
    multiple_venue_research_option: Mapping[str, str]
    required_snapshot_fields: tuple[str, ...]
    required_snapshot_fields_scope: str
    selected_native_snapshot_fields: tuple[str, ...]
    generic_cross_venue_projection_available: bool
    selected_impact_reference: str
    selected_side_impact_includes_crossing_half_spread: bool
    standalone_spread_addition_to_selected_side_impact_permitted: bool
    round_trip_impact_requires_entry_and_exit_snapshots: bool
    impact_cost_application_policy_sealed: bool
    selection_blockers: tuple[str, ...]
    operator_decision: str
    implications: tuple[str, ...]
    next_safe_command: str
    authorization_boundary: str
    expected_provider_activity: str
    rollback_disable_command: str
    spread_provider_status: str
    public_market_data_scope_confirmed: bool
    public_market_data_permission_requested: bool
    private_market_data_permission_requested: bool
    order_permission_requested: bool
    trading_permission_requested: bool
    provider_call_planned: bool
    provider_call_attempted: bool
    live_adapter_activated: bool
    credentials_read: bool
    network_called: bool
    writes_performed: bool
    research_only: bool

    def to_dict(self) -> dict[str, object]:
        return _execution_quality_readiness_dict(self)


# Stable public API aliases keep existing imports and annotations intact while
# the implementation classes remain an explicitly closed model bundle.
ExecutionVenueCapability = _ExecutionVenueCapability
ExecutionQualityRequest = _ExecutionQualityRequest
ExecutionQualitySnapshot = _ExecutionQualitySnapshot
ExecutionQualityReader = _ExecutionQualityReader
ExecutionQualityReadiness = _ExecutionQualityReadiness


def _execution_quality_readiness_dict(
    value: _ExecutionQualityReadiness,
) -> dict[str, object]:
    """Project the large immutable contract without inflating its model class."""

    return {
        "contract_version": value.contract_version,
        "status": value.status,
        "selected_venue": value.selected_venue,
        "selected_execution_mode": value.selected_execution_mode,
        "intended_venue": value.intended_venue,
        "intended_instrument_mode": value.intended_instrument_mode,
        "quote_currency": value.quote_currency,
        "primary_cost_currency": value.primary_cost_currency,
        "primary_cost_currency_policy": value.primary_cost_currency_policy,
        "primary_cost_currency_policy_sealed": (
            value.primary_cost_currency_policy_sealed
        ),
        "usd_equivalence_assumed": value.usd_equivalence_assumed,
        "protocol_v2_cost_model_sealed": value.protocol_v2_cost_model_sealed,
        "remaining_protocol_v2_cost_fields": list(
            value.remaining_protocol_v2_cost_fields
        ),
        "fee_rate_authority_status": value.fee_rate_authority_status,
        "public_fee_reference_url": value.public_fee_reference_url,
        "account_fee_rate_endpoint_doc_url": value.account_fee_rate_endpoint_doc_url,
        "account_fee_endpoint_requires_credentials": (
            value.account_fee_endpoint_requires_credentials
        ),
        "account_specific_fee_rate_access_authorized": (
            value.account_specific_fee_rate_access_authorized
        ),
        "official_fee_sources_reviewed_at": value.official_fee_sources_reviewed_at,
        "eligible_instrument_set": list(value.eligible_instrument_set),
        "eligible_instrument_selection_rule": value.eligible_instrument_selection_rule,
        "eligible_instrument_set_frozen": value.eligible_instrument_set_frozen,
        "jurisdiction_and_account_eligibility_confirmation": (
            value.jurisdiction_and_account_eligibility_confirmation
        ),
        "jurisdiction_and_account_eligibility_confirmed": (
            value.jurisdiction_and_account_eligibility_confirmed
        ),
        "expected_public_private_data_boundary": (
            value.expected_public_private_data_boundary
        ),
        "human_decision_confirmed_at": value.human_decision_confirmed_at,
        "required_human_decision_fields": list(value.required_human_decision_fields),
        "human_decision_template": dict(value.human_decision_template),
        "supported_offline_adapters": list(value.supported_offline_adapters),
        "supported_live_adapters": list(value.supported_live_adapters),
        "supported_evidence_stores": list(value.supported_evidence_stores),
        "immutable_capture_contract_implemented": (
            value.immutable_capture_contract_implemented
        ),
        "protocol_v2_annex_bound": value.protocol_v2_annex_bound,
        "protocol_v2_evidence_eligible": value.protocol_v2_evidence_eligible,
        "supported_interface_modes": list(value.supported_interface_modes),
        "feasible_venues": [row.to_dict() for row in value.feasible_venues],
        "multiple_venue_research_option": dict(
            value.multiple_venue_research_option
        ),
        "required_snapshot_fields": list(value.required_snapshot_fields),
        "required_snapshot_fields_scope": value.required_snapshot_fields_scope,
        "selected_native_snapshot_fields": list(value.selected_native_snapshot_fields),
        "generic_cross_venue_projection_available": (
            value.generic_cross_venue_projection_available
        ),
        "selected_impact_reference": value.selected_impact_reference,
        "selected_side_impact_includes_crossing_half_spread": (
            value.selected_side_impact_includes_crossing_half_spread
        ),
        "standalone_spread_addition_to_selected_side_impact_permitted": (
            value.standalone_spread_addition_to_selected_side_impact_permitted
        ),
        "round_trip_impact_requires_entry_and_exit_snapshots": (
            value.round_trip_impact_requires_entry_and_exit_snapshots
        ),
        "impact_cost_application_policy_sealed": (
            value.impact_cost_application_policy_sealed
        ),
        "selection_blockers": list(value.selection_blockers),
        "operator_decision": value.operator_decision,
        "implications": list(value.implications),
        "next_safe_command": value.next_safe_command,
        "authorization_boundary": value.authorization_boundary,
        "expected_provider_activity": value.expected_provider_activity,
        "rollback_disable_command": value.rollback_disable_command,
        "spread_provider_status": value.spread_provider_status,
        "public_market_data_scope_confirmed": (
            value.public_market_data_scope_confirmed
        ),
        "public_market_data_permission_requested": (
            value.public_market_data_permission_requested
        ),
        "private_market_data_permission_requested": (
            value.private_market_data_permission_requested
        ),
        "order_permission_requested": value.order_permission_requested,
        "trading_permission_requested": value.trading_permission_requested,
        "provider_call_planned": value.provider_call_planned,
        "provider_call_attempted": value.provider_call_attempted,
        "live_adapter_activated": value.live_adapter_activated,
        "credentials_read": value.credentials_read,
        "network_called": value.network_called,
        "writes_performed": value.writes_performed,
        "research_only": value.research_only,
    }


_COMMON_OPERATOR_INPUTS = (
    "intended_execution_venue",
    "intended_execution_mode",
    "exact_instrument_or_pair",
    "quote_currency",
    "eligible_instrument_set",
    "jurisdiction_and_account_eligibility_confirmation",
    "expected_public_private_data_boundary",
    "maximum_read_request_budget",
)
_COMMON_JURISDICTION = (
    "operator_must_confirm_current_venue_and_account_eligibility",
    "public_market_data_reachability_does_not_imply_trading_eligibility",
)
_COMMON_NETWORK = (
    "operator_must_confirm_the_official_endpoint_is_permitted_and_reachable",
    "rate_limit_or_region_failures_must_fail_closed_without_bypass",
)


VENUE_CAPABILITIES = (
    ExecutionVenueCapability(
        venue_id="binance",
        display_name="Binance",
        implementation_status="feasible_not_implemented",
        execution_modes=("spot", "perpetual"),
        market_data_access="public_market_data_no_credentials_expected",
        public_endpoint_expected=True,
        credentials_required=(),
        required_operator_inputs=_COMMON_OPERATOR_INPUTS,
        jurisdiction_constraints=_COMMON_JURISDICTION,
        network_constraints=_COMMON_NETWORK + (
            "WAF_and_IP_policy_must_be_respected",
        ),
        request_limits=(
            "dynamic_request_weight_from_exchange_info_and_response_headers",
            "back_off_on_429_and_never_continue_into_418_IP_ban",
        ),
        expected_metrics=COMMON_METRICS,
        official_source_urls=(
            "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints",
            "https://developers.binance.com/en/docs/products/spot/rest-api",
            "https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Order-Book",
        ),
        official_sources_reviewed_at="2026-07-15",
    ),
    ExecutionVenueCapability(
        venue_id="bybit",
        display_name="Bybit",
        implementation_status=(
            "selected_public_REST_adapter_ready_inactive_live_egress_reachability_unverified"
        ),
        execution_modes=("spot", "perpetual"),
        market_data_access="public_market_data_no_credentials_expected",
        public_endpoint_expected=True,
        credentials_required=(),
        required_operator_inputs=_COMMON_OPERATOR_INPUTS,
        jurisdiction_constraints=_COMMON_JURISDICTION + (
            "do_not_treat_a_public_endpoint_as_permission_to_use_the_venue",
        ),
        network_constraints=_COMMON_NETWORK + (
            "current_project_egress_has_recorded_a_region_restricted_403",
            "no_proxy_VPN_or_region_bypass_is_authorized",
        ),
        request_limits=(
            "default_HTTP_IP_limit_600_requests_per_5_seconds",
            "use_a_much_lower_bounded_project_budget_and_honor_backoff",
        ),
        expected_metrics=BYBIT_NATIVE_METRICS,
        official_source_urls=(
            "https://bybit-exchange.github.io/docs/v5/market/instrument",
            "https://bybit-exchange.github.io/docs/v5/market/orderbook",
            "https://bybit-exchange.github.io/docs/v5/rate-limit",
        ),
        official_sources_reviewed_at="2026-07-17",
    ),
    ExecutionVenueCapability(
        venue_id="coinbase_exchange",
        display_name="Coinbase Exchange",
        implementation_status="feasible_not_implemented",
        execution_modes=("spot",),
        market_data_access="public_market_data_no_credentials_expected",
        public_endpoint_expected=True,
        credentials_required=(),
        required_operator_inputs=_COMMON_OPERATOR_INPUTS,
        jurisdiction_constraints=_COMMON_JURISDICTION,
        network_constraints=_COMMON_NETWORK,
        request_limits=(
            "public_REST_10_requests_per_second_per_IP",
            "public_REST_burst_up_to_15_requests_per_second_per_IP",
        ),
        expected_metrics=COMMON_METRICS + ("order_book_sequence",),
        official_source_urls=(
            "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book",
            "https://docs.cdp.coinbase.com/exchange/rest-api/rate-limits",
        ),
        official_sources_reviewed_at="2026-07-15",
    ),
    ExecutionVenueCapability(
        venue_id="kraken",
        display_name="Kraken",
        implementation_status="feasible_not_implemented_limited_depth",
        execution_modes=("spot",),
        market_data_access="public_market_data_no_credentials_expected",
        public_endpoint_expected=True,
        credentials_required=(),
        required_operator_inputs=_COMMON_OPERATOR_INPUTS,
        jurisdiction_constraints=_COMMON_JURISDICTION,
        network_constraints=_COMMON_NETWORK,
        request_limits=(
            "official_guidance_says_1_public_request_per_second_or_less_stays_within_limits",
            "returned_pre_trade_depth_is_top_10_levels_and_must_be_labeled_truncated",
        ),
        expected_metrics=COMMON_METRICS + ("depth_truncated",),
        official_source_urls=(
            "https://docs.kraken.com/api/docs/rest-api/get-pre-trade/",
            "https://support.kraken.com/hc/articles/206548367",
        ),
        official_sources_reviewed_at="2026-07-15",
    ),
    ExecutionVenueCapability(
        venue_id="dex_operator_selected",
        display_name="Operator-selected DEX router or pool",
        implementation_status="interface_ready_provider_not_selected",
        execution_modes=("dex",),
        market_data_access="unknown_until_chain_and_provider_are_selected",
        public_endpoint_expected=None,
        credentials_required=("provider_specific_if_required",),
        required_operator_inputs=_COMMON_OPERATOR_INPUTS + (
            "chain_id",
            "base_and_quote_token_contracts",
            "pool_or_router_identity",
            "block_freshness_policy",
            "gas_and_route_assumptions",
        ),
        jurisdiction_constraints=_COMMON_JURISDICTION,
        network_constraints=(
            "chain_RPC_or_quote_provider_not_selected",
            "chain_pool_router_token_and_block_identity_are_required",
            "cross_chain_and_wrapped_asset_identity_must_fail_closed",
        ),
        request_limits=(
            "unknown_until_operator_selects_the_chain_router_and_data_provider",
        ),
        expected_metrics=COMMON_METRICS + (
            "chain_id",
            "block_number",
            "pool_or_router_id",
            "gas_estimate_native",
            "route_identity",
        ),
        official_source_urls=(),
        official_sources_reviewed_at="2026-07-15",
    ),
)


def build_execution_quality_readiness() -> ExecutionQualityReadiness:
    """Return deterministic static readiness without inspecting ambient state."""

    return ExecutionQualityReadiness(
        contract_version=CONTRACT_VERSION,
        status="execution_surface_selected_capture_contract_ready_inactive",
        selected_venue="bybit",
        selected_execution_mode="perpetual",
        intended_venue="bybit",
        intended_instrument_mode="perpetual",
        quote_currency="USDT",
        primary_cost_currency="USDT",
        primary_cost_currency_policy=(
            "native_USDT_only_no_USD_conversion_or_equivalence"
        ),
        primary_cost_currency_policy_sealed=True,
        usd_equivalence_assumed=False,
        protocol_v2_cost_model_sealed=False,
        remaining_protocol_v2_cost_fields=REMAINING_PROTOCOL_V2_COST_FIELDS,
        fee_rate_authority_status=(
            "unsealed_public_reference_not_account_authoritative_authenticated_"
            "account_endpoint_outside_public_only_scope"
        ),
        public_fee_reference_url=OFFICIAL_PUBLIC_FEE_REFERENCE_URL,
        account_fee_rate_endpoint_doc_url=(
            OFFICIAL_ACCOUNT_FEE_RATE_ENDPOINT_DOC_URL
        ),
        account_fee_endpoint_requires_credentials=True,
        account_specific_fee_rate_access_authorized=False,
        official_fee_sources_reviewed_at="2026-07-19",
        eligible_instrument_set=(),
        eligible_instrument_selection_rule=(
            "top_30_liquid_decision_radar_assets_intersect_active_bybit_USDT_"
            "linear_perpetuals_then_freeze_exact_set_in_protocol_v2_annex"
        ),
        eligible_instrument_set_frozen=False,
        jurisdiction_and_account_eligibility_confirmation=(
            "owner_confirmed_2026-07-17_for_bybit_USDT_linear_perpetual_"
            "research_scope"
        ),
        jurisdiction_and_account_eligibility_confirmed=True,
        expected_public_private_data_boundary=(
            "public_market_data_only_no_credentials_no_private_data"
        ),
        human_decision_confirmed_at="2026-07-17",
        required_human_decision_fields=REMAINING_PROTOCOL_V2_SEALING_FIELDS,
        human_decision_template=(
            ("intended_venue", "bybit"),
            ("instrument_mode", "perpetual"),
            ("quote_currency", "USDT"),
            (
                "eligible_instrument_set",
                "pending_exact_annex_freeze_from_confirmed_selection_rule",
            ),
            (
                "jurisdiction_and_account_eligibility_confirmation",
                "confirmed_2026-07-17_by_owner_for_research_scope",
            ),
            (
                "expected_public_private_data_boundary",
                "public_market_data_only_no_credentials_no_private_data",
            ),
        ),
        supported_offline_adapters=(
            "bybit_usdt_linear_perpetual_fixture_normalizer_v2",
        ),
        supported_live_adapters=(
            "bybit_usdt_linear_perpetual_public_REST_capture_v4",
        ),
        supported_evidence_stores=(
            "immutable_raw_response_manifest_receipt_pointer_v4",
        ),
        immutable_capture_contract_implemented=True,
        protocol_v2_annex_bound=False,
        protocol_v2_evidence_eligible=False,
        supported_interface_modes=EXECUTION_MODES,
        feasible_venues=VENUE_CAPABILITIES,
        multiple_venue_research_option=MULTI_VENUE_RESEARCH_OPTION,
        required_snapshot_fields=REQUIRED_SNAPSHOT_FIELDS,
        required_snapshot_fields_scope=(
            "inactive_generic_cross_venue_interface_not_selected_bybit_native_contract"
        ),
        selected_native_snapshot_fields=BYBIT_NATIVE_METRICS,
        generic_cross_venue_projection_available=False,
        selected_impact_reference="mid_price",
        selected_side_impact_includes_crossing_half_spread=True,
        standalone_spread_addition_to_selected_side_impact_permitted=False,
        round_trip_impact_requires_entry_and_exit_snapshots=True,
        impact_cost_application_policy_sealed=False,
        selection_blockers=(
            "eligible_instrument_set_not_frozen",
            "bybit_public_endpoint_reachability_unverified_after_recorded_403",
            "runtime_provider_authorization_not_created_by_operator_selection",
            "protocol_v2_cost_model_not_sealed",
            "protocol_v2_annex_not_sealed",
        ),
        operator_decision=(
            "confirmed_bybit_USDT_linear_perpetual_public_market_data_only"
        ),
        implications=(
            "Bybit_USDT_perpetual_books_define_the_primary_spread_depth_and_impact_surface",
            "the_exact_top_30_intersection_must_be_frozen_before_holdout_access",
            "public_data_scope_does_not_activate_a_provider_call_or_trading_path",
            "the_recorded_403_must_fail_closed_without_proxy_VPN_or_region_bypass",
            "primary_cost_depth_and_impact_currency_is_native_USDT_without_USD_equivalence",
            "selected_bybit_capability_uses_only_native_USDT_depth_and_notional_fields",
            "generic_USD_projection_is_inactive_and_unavailable",
            "side_specific_visible_book_impact_from_mid_already_includes_half_spread",
            "adding_standalone_spread_to_the_same_side_impact_would_double_count",
            "public_reference_fee_tables_do_not_prove_account_or_symbol_specific_rates",
            "authenticated_account_fee_access_is_outside_the_confirmed_public_only_scope",
            "fresh_capture_quality_does_not_become_protocol_v2_evidence_before_annex_binding",
        ),
        next_safe_command=(
            "make radar-execution-quality-bybit-readiness PYTHON=.venv/bin/python"
        ),
        authorization_boundary=(
            "the_operator_choice_confirms_public_only_research_scope_but_does_not_"
            "create_runtime_provider_authorization_or_permit_private_data_orders_or_trading"
        ),
        expected_provider_activity="none_static_readiness_only",
        rollback_disable_command=(
            "unset_RSI_DECISION_RADAR_BYBIT_EXECUTION_QUALITY_LIVE_if_later_enabled"
        ),
        spread_provider_status=(
            "bybit_immutable_capture_ready_inactive_live_spread_unavailable"
        ),
        public_market_data_scope_confirmed=True,
        public_market_data_permission_requested=False,
        private_market_data_permission_requested=False,
        order_permission_requested=False,
        trading_permission_requested=False,
        provider_call_planned=False,
        provider_call_attempted=False,
        live_adapter_activated=False,
        credentials_read=False,
        network_called=False,
        writes_performed=False,
        research_only=True,
    )


def format_execution_quality_readiness(result: ExecutionQualityReadiness) -> str:
    """Render the confirmed selection and remaining fail-closed boundaries."""

    lines = [
        "CRYPTO DECISION RADAR EXECUTION-QUALITY READINESS",
        f"status={result.status}",
        f"selected_venue={result.selected_venue} "
        f"selected_execution_mode={result.selected_execution_mode}",
        f"intended_venue={result.intended_venue} "
        f"intended_instrument_mode={result.intended_instrument_mode}",
        f"quote_currency={result.quote_currency} eligible_instrument_set=not_yet_frozen",
        f"primary_cost_currency={result.primary_cost_currency} "
        "primary_cost_currency_policy_sealed="
        f"{str(result.primary_cost_currency_policy_sealed).casefold()}",
        f"primary_cost_currency_policy={result.primary_cost_currency_policy} "
        f"usd_equivalence_assumed={str(result.usd_equivalence_assumed).casefold()}",
        "protocol_v2_cost_model_sealed="
        f"{str(result.protocol_v2_cost_model_sealed).casefold()}",
        "remaining_protocol_v2_cost_fields="
        + ",".join(result.remaining_protocol_v2_cost_fields),
        f"fee_rate_authority_status={result.fee_rate_authority_status}",
        f"public_fee_reference_url={result.public_fee_reference_url}",
        "account_fee_rate_endpoint_doc_url="
        f"{result.account_fee_rate_endpoint_doc_url}",
        "account_fee_endpoint_requires_credentials="
        f"{str(result.account_fee_endpoint_requires_credentials).casefold()} "
        "account_specific_fee_rate_access_authorized="
        f"{str(result.account_specific_fee_rate_access_authorized).casefold()}",
        f"official_fee_sources_reviewed_at={result.official_fee_sources_reviewed_at}",
        f"required_snapshot_fields_scope={result.required_snapshot_fields_scope}",
        "selected_native_snapshot_fields="
        + ",".join(result.selected_native_snapshot_fields),
        "generic_cross_venue_projection_available="
        f"{str(result.generic_cross_venue_projection_available).casefold()}",
        f"selected_impact_reference={result.selected_impact_reference}",
        "selected_side_impact_includes_crossing_half_spread="
        f"{str(result.selected_side_impact_includes_crossing_half_spread).casefold()}",
        "standalone_spread_addition_to_selected_side_impact_permitted="
        f"{str(result.standalone_spread_addition_to_selected_side_impact_permitted).casefold()}",
        "round_trip_impact_requires_entry_and_exit_snapshots="
        f"{str(result.round_trip_impact_requires_entry_and_exit_snapshots).casefold()} "
        "impact_cost_application_policy_sealed="
        f"{str(result.impact_cost_application_policy_sealed).casefold()}",
        f"eligible_instrument_selection_rule={result.eligible_instrument_selection_rule}",
        f"eligible_instrument_set_frozen={str(result.eligible_instrument_set_frozen).casefold()}",
        "jurisdiction_and_account_eligibility_confirmed=true "
        f"confirmed_at={result.human_decision_confirmed_at}",
        "expected_public_private_data_boundary="
        f"{result.expected_public_private_data_boundary}",
        "supported_offline_adapters=" + ",".join(result.supported_offline_adapters),
        "supported_live_adapters=" + ",".join(result.supported_live_adapters),
        "supported_evidence_stores=" + ",".join(result.supported_evidence_stores),
        "immutable_capture_contract_implemented="
        f"{str(result.immutable_capture_contract_implemented).casefold()} "
        "protocol_v2_annex_bound="
        f"{str(result.protocol_v2_annex_bound).casefold()} "
        "protocol_v2_evidence_eligible="
        f"{str(result.protocol_v2_evidence_eligible).casefold()}",
        "read_only=true provider_calls=0 provider_call_planned=false provider_call_attempted=false",
        "credentials_read=false network_called=false writes_performed=false",
        "research_only=true",
        f"operator_decision={result.operator_decision}",
        f"next_safe_command={result.next_safe_command}",
        f"authorization_boundary={result.authorization_boundary}",
        f"expected_provider_activity={result.expected_provider_activity}",
        f"rollback_disable_command={result.rollback_disable_command}",
        f"spread_provider_status={result.spread_provider_status}",
        "public_market_data_scope_confirmed=true",
        "public_market_data_permission_requested=false "
        "private_market_data_permission_requested=false",
        "order_permission_requested=false trading_permission_requested=false",
        "remaining_human_sealing_fields="
        + ",".join(result.required_human_decision_fields),
        "",
        "CONFIRMED EXECUTION-QUALITY DECISION (no order permission):",
        *(f"{key}={value}" for key, value in result.human_decision_template),
        "",
        "Feasibility catalog (Bybit perpetual is selected; alternatives are inactive):",
    ]
    for mode in result.supported_interface_modes:
        venue_ids = ",".join(
            venue.venue_id
            for venue in result.feasible_venues
            if mode in venue.execution_modes
        )
        public_read, authorization = _MODE_ACCESS[mode]
        lines.extend(
            (
                f"- {mode}: venues={venue_ids}",
                f"  public_read={public_read}",
                f"  authorization={authorization}",
            )
        )
    lines.extend(
        (
            "",
            "Execution-quality unit boundary:",
            "- selected_bybit_offline=best_bid,best_ask,mid_price,spread_bps,bid_depth_usdt_by_band,ask_depth_usdt_by_band,buy_price_impact_bps_by_notional_usdt,sell_price_impact_bps_by_notional_usdt",
            "- primary_protocol_v2_cost_unit=USDT;native_quote_only=true;USD_equivalence_assumed=false",
            "- future_generic_USD_projection=outside_primary_protocol_v2_cost_surface_and_unavailable_without_a_separate_explicit_conversion_policy",
            "- generic_cross_venue_fields_if_later_converted=bid_depth_usd_by_band,ask_depth_usd_by_band,buy_price_impact_bps_by_notional,sell_price_impact_bps_by_notional",
            "- freshness_and_lineage=provider_observed_at,acquired_at,freshness_status,source_url,request_lineage_id",
            "- set_freshness=every_book_fresh_at_capture_completion;maximum_provider_observation_age_seconds=15;protocol_v2_input_quality_uses_completion_freshness",
            "- dex_additions=chain_id,block_number,pool_or_router_id,gas_estimate_native,route_identity",
            "",
            "Multiple-venue research alternative (not an execution venue):",
            "- "
            + "; ".join(
                f"{key}={value}"
                for key, value in result.multiple_venue_research_option.items()
            ),
            "",
            "Feasible candidates (only Bybit perpetual is selected; none is live-activated):",
        )
    )
    for venue in result.feasible_venues:
        credentials = ",".join(venue.credentials_required) or "none_for_expected_public_market_data"
        sources = ",".join(venue.official_source_urls) or "provider_not_selected"
        public_endpoint = (
            "unknown"
            if venue.public_endpoint_expected is None
            else str(venue.public_endpoint_expected).casefold()
        )
        lines.extend(
            (
                f"- {venue.venue_id}: status={venue.implementation_status} "
                f"modes={','.join(venue.execution_modes)}",
                f"  access={venue.market_data_access} public_endpoint_expected={public_endpoint} "
                f"read_credentials={credentials}",
                f"  limits={';'.join(venue.request_limits)}",
                f"  metrics={','.join(venue.expected_metrics)}",
                f"  prerequisites={','.join(venue.required_operator_inputs)}",
                f"  jurisdiction={','.join(venue.jurisdiction_constraints)}",
                f"  network={','.join(venue.network_constraints)}",
                f"  official_sources={sources}",
                f"  official_sources_reviewed_at={venue.official_sources_reviewed_at}",
            )
        )
    lines.extend(
        (
            "",
            "Bybit USDT-linear perpetuals are selected for public-data research and "
            "the bounded adapter is implemented but inactive. No provider call, "
            "credential read, live-adapter activation, private-data read, trade, "
            "order, or execution action is authorized by this static report.",
        )
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report static execution-quality feasibility without provider calls."
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    readiness = build_execution_quality_readiness()
    if args.as_json:
        print(json.dumps(readiness.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_execution_quality_readiness(readiness))
    return 0


__all__ = (
    "COMMON_METRICS",
    "CONTRACT_VERSION",
    "EXECUTION_MODES",
    "MULTI_VENUE_RESEARCH_OPTION",
    "ExecutionQualityReadiness",
    "ExecutionQualityReader",
    "ExecutionQualityRequest",
    "ExecutionQualitySnapshot",
    "ExecutionVenueCapability",
    "REQUIRED_SNAPSHOT_FIELDS",
    "VENUE_CAPABILITIES",
    "build_execution_quality_readiness",
    "format_execution_quality_readiness",
    "main",
)


if __name__ == "__main__":
    raise SystemExit(main())
