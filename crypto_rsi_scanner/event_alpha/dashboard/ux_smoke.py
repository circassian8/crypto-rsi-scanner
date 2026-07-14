"""Offline semantic UX contract smoke for the read-only Decision Radar."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from .__main__ import _fixture_smoke_now
from .loader import candidate_identifier, load_dashboard_snapshot
from .render import render_dashboard_page


_PRIMARY_ROUTES = (
    "/",
    "/market-radar",
    "/ideas",
    "/calendar",
    "/health",
    "/outcomes",
    "/campaign-history",
)


@dataclass
class _SemanticDocument:
    viewport: bool = False
    skip_link: bool = False
    navigation: bool = False
    main: bool = False
    research_guard: bool = False


class _ContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.document = _SemanticDocument()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())
        if tag == "meta" and values.get("name") == "viewport":
            self.document.viewport = True
        if tag == "a" and "skip-link" in classes and values.get("href") == "#main-content":
            self.document.skip_link = True
        if tag == "nav" and values.get("aria-label") == "Primary":
            self.document.navigation = True
        if tag == "main" and values.get("id") == "main-content":
            self.document.main = True

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split()).casefold()
        if "human decision required" in normalized:
            self.document.research_guard = True


def run_ux_smoke(
    artifact_base: str | Path,
    namespace: str,
    *,
    now: str | None = None,
) -> int:
    """Render the primary product surface and fail on semantic shell drift."""

    base = Path(artifact_base)
    snapshot = load_dashboard_snapshot(
        base,
        namespace,
        now=now or _fixture_smoke_now(base, namespace),
    )
    if not snapshot.generation_authoritative:
        raise SystemExit("radar dashboard UX smoke requires an authoritative generation")
    routes = list(_PRIMARY_ROUTES)
    first_id = next(
        (
            candidate_identifier(row)
            for row in snapshot.visible_current_candidates
            if candidate_identifier(row)
        ),
        "",
    )
    if first_id:
        routes.append(f"/ideas/{first_id}")
    for route in routes:
        response = render_dashboard_page(snapshot, route, include_diagnostics=True)
        if response.status_code != 200:
            raise SystemExit(f"radar dashboard UX smoke failed: {route} status={response.status_code}")
        _check_document(response.body, route, snapshot.run_id, snapshot.revision)
    print(
        "radar_dashboard_ux_smoke: "
        f"pages={len(routes)} semantic_shell=ok responsive_css_contract=ok "
        f"run_id={snapshot.run_id} revision={snapshot.revision} writes=0"
    )
    return 0


def _check_document(body: str, route: str, run_id: str, revision: int) -> None:
    parser = _ContractParser()
    parser.feed(body)
    missing = tuple(
        name
        for name, value in vars(parser.document).items()
        if value is not True
    )
    if missing:
        raise SystemExit(
            f"radar dashboard UX smoke failed: {route} missing={','.join(missing)}"
        )
    required = (
        run_id,
        f"revision {revision}",
        "Research idea, not a trade instruction",
        "@media",
        "overflow-wrap",
    )
    absent = tuple(value for value in required if value not in body)
    if absent:
        raise SystemExit(
            f"radar dashboard UX smoke failed: {route} absent={','.join(absent)}"
        )
    if any(token in body for token in (">None<", ">nan<", ">null<")):
        raise SystemExit(f"radar dashboard UX smoke failed: {route} leaked raw missing values")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-base", default="event_fade_cache")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--now", default=None)
    args = parser.parse_args(argv)
    return run_ux_smoke(args.artifact_base, args.namespace, now=args.now)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ("run_ux_smoke",)
