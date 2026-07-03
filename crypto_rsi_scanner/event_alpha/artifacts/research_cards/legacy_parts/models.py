"""Models helpers for legacy research cards."""

from __future__ import annotations

from .runtime import *

@dataclass(frozen=True)
class EventResearchCardResult:
    key: str
    markdown: str
    found: bool

@dataclass(frozen=True)
class EventResearchCardWriteResult:
    out_dir: Path
    cards_written: int
    index_path: Path
    card_paths: tuple[Path, ...]

def card_index_group(path: Path, *, card_groups: Mapping[Path | str, str] | None = None) -> str:
    """Return the operator-facing research-card group for an existing card file."""
    return _card_index_group(Path(path), card_groups=card_groups)

def card_group_for_opportunity_lane(value: object) -> str | None:
    """Return the lane-first card group for an Event Alpha opportunity lane."""
    return _lane_card_group(value)

def card_index_group_map(paths: Iterable[str | Path]) -> dict[Path, str]:
    """Return card groups, preferring the local index.md when available."""
    cards = [Path(path) for path in paths]
    out: dict[Path, str] = {}
    for index_path in _candidate_index_paths(cards):
        out.update(_parse_index_groups(index_path))
    for path in cards:
        if path.name == "index.md":
            continue
        out.setdefault(path, _card_index_group(path))
    return out

def collapse_card_paths_for_group(
    paths: Iterable[str | Path],
    *,
    group_name: str | None = None,
    card_groups: Mapping[Path | str, str] | None = None,
) -> tuple[tuple[Path, int], ...]:
    """Collapse related card paths into primary card plus hidden count."""
    grouped: dict[tuple[str, str, str, str], list[Path]] = {}
    for value in paths:
        path = Path(value)
        key = _card_family_key(path, group_name=group_name, card_groups=card_groups)
        grouped.setdefault(key, []).append(path)
    collapsed: list[tuple[Path, int]] = []
    for items in grouped.values():
        ordered = sorted(items, key=_card_primary_sort_key)
        collapsed.append((ordered[0], max(0, len(ordered) - 1)))
    return tuple(sorted(collapsed, key=lambda item: item[0].name))

__all__ = (
    'EventResearchCardResult',
    'EventResearchCardWriteResult',
    'card_index_group',
    'card_group_for_opportunity_lane',
    'card_index_group_map',
    'collapse_card_paths_for_group',
)
