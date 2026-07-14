"""Responsive, input-mode, motion, and print dashboard styles."""

from __future__ import annotations


RESPONSIVE_CSS = r"""
@media (max-width: 62rem) {
  .app-shell {
    grid-template-columns: minmax(0, 1fr);
  }

  .app-rail {
    position: static;
    height: auto;
    padding: var(--space-3) var(--space-4);
    overflow: visible;
    border-inline-end: 0;
    border-block-end: 1px solid var(--color-border);
  }

  .app-rail .primary-nav {
    display: flex;
  }

  .app-rail .primary-nav a {
    justify-content: center;
  }

  .rail-safety {
    display: none;
  }

  .app-workspace > .topbar {
    position: static;
  }

  .topbar,
  .page-header {
    align-items: flex-start;
  }

  nav,
  .primary-nav {
    width: 100%;
  }

  nav a,
  .primary-nav a {
    flex: 1 1 10rem;
  }
}

@media (max-width: 45rem) {
  body {
    font-size: 0.9rem;
  }

  header,
  main,
  .site-header,
  .app-main {
    padding-inline: var(--space-3);
  }

  nav,
  .primary-nav {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  nav a,
  .primary-nav a {
    min-width: 0;
    padding-inline: var(--space-2);
    text-align: center;
  }

  .panel,
  .card,
  section,
  .banner,
  .scope,
  .authority-untrusted {
    padding: var(--space-4);
    border-radius: var(--radius-md);
  }

  .definition-list,
  dl {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-1);
  }

  .definition-list dd,
  dd {
    margin-block-end: var(--space-3);
  }

  .table-scroll {
    overflow-x: hidden;
    border: 0;
    background: transparent;
  }

  .data-table.mobile-cards {
    display: block;
    min-width: 0;
    border-collapse: separate;
  }

  .responsive-table {
    display: block;
    min-width: 0;
    border-collapse: separate;
  }

  .responsive-table thead {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  .responsive-table tbody {
    display: grid;
    min-width: 0;
    gap: var(--space-3);
  }

  .responsive-table tr {
    display: grid;
    min-width: 0;
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface-soft);
  }

  .responsive-table td {
    display: grid;
    width: 100%;
    min-width: 0;
    grid-template-columns: minmax(6.5rem, 38%) minmax(0, 1fr);
    gap: var(--space-3);
    padding: var(--space-3);
    overflow-wrap: anywhere;
    border-block-end: 1px solid var(--color-border);
  }

  .responsive-table td::before {
    color: var(--color-text-muted);
    font-size: 0.7rem;
    font-weight: 800;
    letter-spacing: 0.035em;
    text-transform: uppercase;
    content: attr(data-label);
  }

  .responsive-table tr > :last-child {
    border-block-end: 0;
  }

  .page-intro,
  .command-hero,
  .idea-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .count-badge,
  .hero-pulse {
    width: 5.5rem;
    height: 5.5rem;
  }

  .two-column {
    grid-template-columns: minmax(0, 1fr);
  }

  .layer-funnel {
    grid-template-columns: minmax(0, 1fr);
  }

  .funnel-arrow {
    justify-self: center;
    transform: rotate(90deg);
  }

  .mini-score-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-search {
    grid-column: auto;
  }

  .technical-grid,
  .definition-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .idea-expiry {
    width: 100%;
    text-align: left;
  }

  .mobile-cards thead {
    position: absolute;
    width: 1px;
    height: 1px;
    margin: -1px;
    padding: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }

  .mobile-cards tbody {
    display: grid;
    min-width: 0;
    gap: var(--space-3);
  }

  .mobile-cards tr {
    display: grid;
    min-width: 0;
    overflow: hidden;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface-soft);
  }

  .mobile-cards td,
  .mobile-cards th[scope="row"] {
    display: grid;
    width: 100%;
    min-width: 0;
    grid-template-columns: minmax(6.5rem, 38%) minmax(0, 1fr);
    gap: var(--space-3);
    padding: var(--space-3);
    overflow-wrap: anywhere;
    border-block-end: 1px solid var(--color-border);
  }

  .mobile-cards td::before,
  .mobile-cards th[scope="row"]::before {
    content: attr(data-label);
    color: var(--color-text-muted);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.035em;
    text-transform: uppercase;
  }

  .mobile-cards tr > :last-child {
    border-block-end: 0;
  }

  .candidate-filters,
  .filter-bar {
    display: grid;
    align-items: stretch;
    grid-template-columns: minmax(0, 1fr);
  }

  .candidate-filters label,
  .filter-bar label,
  .candidate-filters input,
  .candidate-filters select,
  .candidate-filters button,
  .filter-bar input,
  .filter-bar select,
  .filter-bar button {
    width: 100%;
  }
}

@media (max-width: 25rem) {
  .mobile-cards td,
  .mobile-cards th[scope="row"] {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-1);
  }

  .responsive-table td {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-1);
  }
}

@media (pointer: coarse) {
  a,
  button,
  input,
  select,
  summary {
    min-height: var(--touch-target);
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

@media print {
  :root {
    color-scheme: light;
  }

  body {
    background: #fff;
    color: #111827;
  }

  nav,
  .primary-nav,
  .skip-link,
  .candidate-filters,
  .filter-bar {
    display: none !important;
  }

  .panel,
  .card,
  section {
    break-inside: avoid;
    box-shadow: none;
  }
}
""".strip()


__all__ = ("RESPONSIVE_CSS",)
