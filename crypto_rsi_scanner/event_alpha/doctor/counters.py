"""Counter model for Event Alpha doctor checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass
class DoctorCounterSet:
    counters: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "DoctorCounterSet":
        counters: dict[str, int] = {}
        for key, value in values.items():
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                counters[str(key)] = value
        return cls(counters)

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + int(amount)

    def get(self, name: str, default: int = 0) -> int:
        return self.counters.get(name, default)

    def to_dict(self) -> dict[str, int]:
        return dict(self.counters)
