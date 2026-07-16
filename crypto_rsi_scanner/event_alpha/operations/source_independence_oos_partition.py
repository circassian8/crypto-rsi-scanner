"""Partition-isolation checks for source-independence OOS corpora."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def cross_split_leakage_errors(
    rows: Sequence[object], *, allowed_splits: Sequence[str]
) -> list[str]:
    """Reject family, exact-source, or exact-content reuse across splits."""

    family_splits: dict[str, set[str]] = {}
    source_digest_splits: dict[str, set[str]] = {}
    content_digest_splits: dict[str, set[str]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("split") not in allowed_splits:
            continue
        split = str(row["split"])
        family_id = row.get("event_copy_family_id")
        if isinstance(family_id, str) and family_id:
            family_splits.setdefault(family_id, set()).add(split)
        for key in ("source_a_digest", "source_b_digest"):
            digest = row.get(key)
            if isinstance(digest, str) and _SHA256_RE.fullmatch(digest):
                source_digest_splits.setdefault(digest, set()).add(split)
        for key in ("source_a_content_digest", "source_b_content_digest"):
            digest = row.get(key)
            if isinstance(digest, str) and _SHA256_RE.fullmatch(digest):
                content_digest_splits.setdefault(digest, set()).add(split)
    errors: list[str] = []
    if any(len(splits) > 1 for splits in family_splits.values()):
        errors.append("corpus_family_cross_split_leakage")
    if any(len(splits) > 1 for splits in source_digest_splits.values()):
        errors.append("corpus_source_digest_cross_split_leakage")
    if any(len(splits) > 1 for splits in content_digest_splits.values()):
        errors.append("corpus_content_digest_cross_split_leakage")
    return errors


__all__ = ("cross_split_leakage_errors",)
