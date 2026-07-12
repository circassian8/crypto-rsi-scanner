"""Deterministic payload-free telemetry for unified calendar normalization."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .models import CALENDAR_REJECTION_CODES


CALENDAR_NORMALIZATION_CONTRACT_VERSION = 1
CALENDAR_DEDUPE_POLICY = "last_valid_row_wins"


@dataclass(frozen=True)
class UnifiedCalendarNormalizationTelemetry:
    """Payload-free counters for one deterministic normalization pass."""

    contract_version: int
    dedupe_policy: str
    input_rows: int
    accepted_rows: int
    output_rows: int
    duplicate_overwrite_rows: int
    non_mapping_rows: int
    rejected_rows: int
    rejected_reason_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        if (
            isinstance(self.contract_version, bool)
            or not isinstance(self.contract_version, int)
            or self.contract_version != CALENDAR_NORMALIZATION_CONTRACT_VERSION
        ):
            raise ValueError("unsupported calendar normalization contract version")
        if self.dedupe_policy != CALENDAR_DEDUPE_POLICY:
            raise ValueError("unsupported calendar normalization dedupe policy")
        counters = {
            "input_rows": self.input_rows,
            "accepted_rows": self.accepted_rows,
            "output_rows": self.output_rows,
            "duplicate_overwrite_rows": self.duplicate_overwrite_rows,
            "non_mapping_rows": self.non_mapping_rows,
            "rejected_rows": self.rejected_rows,
        }
        if any(not _is_nonnegative_int(value) for value in counters.values()):
            raise ValueError("calendar normalization counters must be non-negative integers")
        if not isinstance(self.rejected_reason_counts, Mapping):
            raise ValueError("calendar rejected reason counts must be a mapping")
        reasons: dict[str, int] = {}
        for raw_reason, count in self.rejected_reason_counts.items():
            if not isinstance(raw_reason, str) or raw_reason not in CALENDAR_REJECTION_CODES:
                raise ValueError("calendar rejected reason code is not registered")
            if not _is_nonnegative_int(count) or count == 0:
                raise ValueError("calendar rejected reason counts must be positive integers")
            reasons[raw_reason] = count
        object.__setattr__(
            self,
            "rejected_reason_counts",
            MappingProxyType(dict(sorted(reasons.items()))),
        )
        if self.input_rows != self.accepted_rows + self.non_mapping_rows + self.rejected_rows:
            raise ValueError("calendar normalization input counter invariant failed")
        if self.accepted_rows != self.output_rows + self.duplicate_overwrite_rows:
            raise ValueError("calendar normalization accepted counter invariant failed")
        if self.rejected_rows != sum(reasons.values()):
            raise ValueError("calendar normalization rejected counter invariant failed")

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON-ready telemetry contract."""

        return {
            "contract_version": self.contract_version,
            "dedupe_policy": self.dedupe_policy,
            "input_rows": self.input_rows,
            "accepted_rows": self.accepted_rows,
            "output_rows": self.output_rows,
            "duplicate_overwrite_rows": self.duplicate_overwrite_rows,
            "non_mapping_rows": self.non_mapping_rows,
            "rejected_rows": self.rejected_rows,
            "rejected_reason_counts": dict(self.rejected_reason_counts),
        }


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


__all__ = (
    "CALENDAR_DEDUPE_POLICY",
    "CALENDAR_NORMALIZATION_CONTRACT_VERSION",
    "UnifiedCalendarNormalizationTelemetry",
)
