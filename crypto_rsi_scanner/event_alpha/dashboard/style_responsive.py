"""Responsive, input-mode, motion, and print dashboard styles."""

from __future__ import annotations


RESPONSIVE_CSS = r"""
@media (max-width: 86rem) {
  .market-desktop-table,
  .outcome-desktop-table,
  .campaign-desktop-table {
    display: none;
  }

  .market-mobile-list,
  .outcome-mobile-list,
  .campaign-mobile-list {
    display: grid;
    gap: var(--space-3);
    margin-block-start: var(--space-3);
  }

  .market-metrics {
    grid-template-columns: repeat(5, minmax(0, 1fr));
  }
}

@media (min-width: 75rem) and (max-width: 86rem) {
  .market-mobile-items {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 70rem) {
  .market-metrics,
  .today-metrics .metric-grid,
  .outcome-metrics .metric-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 62rem) {
  .app-shell {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: auto minmax(0, 1fr);
    align-content: start;
  }

  .app-rail {
    position: sticky;
    inset-block-start: 0;
    display: grid;
    height: auto;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    overflow: visible;
    align-self: start;
    border-inline-end: 0;
    border-block-end: 1px solid var(--color-border);
  }

  .desktop-nav {
    display: none !important;
  }

  .mobile-nav {
    position: relative;
    display: block;
  }

  .mobile-nav > summary {
    display: flex;
    min-height: var(--touch-target);
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    cursor: pointer;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: var(--color-surface-soft);
    color: var(--color-text-muted);
    list-style: none;
  }

  .mobile-nav > summary::-webkit-details-marker {
    display: none;
  }

  .mobile-nav > summary::after {
    color: var(--color-text-subtle);
    content: "▾";
  }

  .mobile-nav > summary span {
    font-size: 0.72rem;
  }

  .mobile-nav > summary strong {
    color: var(--color-text);
  }

  .mobile-nav > nav {
    position: absolute;
    z-index: 60;
    inset-block-start: calc(100% + var(--space-2));
    inset-inline-end: 0;
    display: grid;
    width: min(30rem, calc(100vw - 2rem));
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-md);
    background: var(--color-canvas-raised);
    box-shadow: 0 20px 55px rgb(0 0 0 / 0.45);
  }

  .mobile-nav:not([open]) > nav {
    display: none;
  }

  .mobile-nav[open] > nav {
    display: grid;
  }

  .mobile-nav nav a {
    justify-content: flex-start;
  }

  .rail-safety {
    display: none;
  }

  .app-workspace > .topbar {
    position: static;
    backdrop-filter: none;
  }

  .topbar,
  .page-header {
    align-items: flex-start;
  }

  .topbar-state {
    gap: var(--space-2);
  }

  .decision-thesis .narrative-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .idea-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .market-desktop-table {
    display: none;
  }

  .market-mobile-list {
    display: grid;
    gap: var(--space-3);
  }

  .outcome-desktop-table,
  .campaign-desktop-table {
    display: none;
  }

  .outcome-mobile-list,
  .campaign-mobile-list {
    display: grid;
    gap: var(--space-3);
    margin-block-start: var(--space-3);
  }
}

@media (max-width: 45rem) {
  body {
    font-size: 0.9375rem;
  }

  .market-filters {
    display: block;
  }

  .market-filters > .filter-actions {
    margin-block-start: var(--space-3);
  }

  .anomaly-card__header,
  .anomaly-card__decision {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-1);
  }

  .anomaly-card__metric {
    text-align: start;
  }

  .anomaly-card__metrics {
    width: 100%;
    justify-content: space-between;
    gap: var(--space-3);
  }

  header,
  main,
  .site-header,
  .app-main {
    padding-inline: var(--space-3);
  }

  .brand small {
    display: none;
  }

  .brand-mark {
    width: 2.25rem;
    height: 2.25rem;
  }

  .mobile-nav > summary span {
    display: none;
  }

  .app-workspace > .topbar {
    min-height: 0;
    align-items: center;
    padding-block: var(--space-3);
  }

  .topbar-heading {
    display: block;
  }

  .topbar-heading .eyebrow {
    display: none;
  }

  .topbar-safety {
    display: block;
    margin-block-start: 0.1rem;
    font-size: 0.75rem;
    line-height: 1.25;
  }

  .topbar h1 {
    font-size: 1.25rem;
  }

  .topbar-state {
    width: 100%;
    justify-content: space-between;
  }

  .trust-strip {
    gap: var(--space-1);
  }

  .trust-strip .status-badge {
    font-size: 0.75rem;
  }

  .generation-disclosure > summary {
    padding-inline: var(--space-2);
    font-size: 0.72rem;
  }

  .radar-inline-chart .chart-status,
  .radar-inline-chart .chart-x-label,
  .radar-inline-chart .chart-only-label {
    font-size: 22px;
  }

  .radar-inline-chart .chart-y-label {
    font-size: 20px;
  }

  .generation-popover {
    position: fixed;
    inset: auto var(--space-3) var(--space-3);
    max-height: min(75vh, 34rem);
    width: auto;
    overflow: auto;
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
    overflow-x: auto;
  }

  .data-table.mobile-cards {
    display: block;
    min-width: 0;
    border-collapse: separate;
  }

  .data-table.mobile-cards caption {
    display: block;
    width: 100%;
    max-width: 100%;
    text-align: start;
  }

  .responsive-table {
    min-width: 48rem;
  }

  .market-desktop-table {
    display: none;
  }

  .market-mobile-list {
    display: grid;
    gap: var(--space-3);
  }

  .outcome-desktop-table,
  .campaign-desktop-table {
    display: none;
  }

  .outcome-mobile-list,
  .campaign-mobile-list {
    display: grid;
    gap: var(--space-3);
    margin-block-start: var(--space-3);
  }

  .page-intro,
  .command-hero,
  .idea-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .ideas-intro {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    gap: var(--space-3);
    padding: var(--space-3);
  }

  .ideas-intro .eyebrow {
    margin-block-end: var(--space-1);
  }

  .ideas-intro h2 {
    margin-block-end: var(--space-2);
    font-size: 1.15rem;
  }

  .ideas-intro p:not(.eyebrow) {
    margin: 0;
    font-size: 0.82rem;
    line-height: 1.4;
  }

  .count-badge,
  .hero-pulse {
    display: flex;
    width: auto;
    min-width: 5rem;
    min-height: 0;
    align-items: baseline;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
  }

  .count-badge,
  .hero-pulse span {
    font-size: 1.15rem;
  }

  .count-badge small,
  .hero-pulse small {
    font-size: 0.66rem;
  }

  .ideas-intro .count-badge {
    min-width: 3.5rem;
    flex-direction: column;
    align-items: center;
    gap: 0;
    padding: var(--space-2);
  }

  .idea-filter-disclosure,
  .calendar-filter-disclosure {
    margin-block: var(--space-3);
    padding-inline: var(--space-3);
    border-radius: var(--radius-md);
  }

  .idea-filter-disclosure > summary,
  .calendar-filter-disclosure > summary {
    font-size: 0.86rem;
  }

  .idea-filter-disclosure .disclosure__summary,
  .calendar-filter-disclosure .disclosure__summary {
    font-size: 0.68rem;
  }

  .calendar-coverage--verified {
    gap: var(--space-2);
    padding: var(--space-3);
  }

  .calendar-coverage__heading {
    align-items: flex-start;
  }

  .calendar-coverage__heading .eyebrow {
    margin-block-end: var(--space-1);
    font-size: 0.66rem;
  }

  .calendar-coverage__heading h2 {
    font-size: 1.05rem;
  }

  .calendar-coverage__heading .status-badge {
    max-width: 8.5rem;
    font-size: 0.75rem;
    text-align: center;
  }

  .calendar-coverage__receipt {
    font-size: 0.76rem;
    line-height: 1.4;
  }

  .calendar-coverage--verified > .disclosure > summary {
    font-size: 0.74rem;
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

  .attention-card__scores {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .score-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .score-card:first-child {
    grid-column: 1 / -1;
  }

  .score-card p {
    min-height: 0;
  }

  .filter-search {
    grid-column: auto;
  }

  .filter-grid-primary,
  .filter-grid-advanced {
    grid-template-columns: minmax(0, 1fr);
  }

  .metric-card {
    min-height: 5rem;
    padding: var(--space-3);
  }

  .metric-card strong {
    font-size: 1.35rem;
  }

  .outcome-metrics .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .market-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--space-2);
  }

  .market-metrics .metric-card {
    min-height: 4.5rem;
    padding: var(--space-2);
  }

  .market-metrics .metric-card span {
    font-size: 0.68rem;
  }

  .market-metrics .metric-card small {
    display: none;
  }

  .market-metrics .metric-card strong {
    font-size: 1.15rem;
  }

  .market-mobile-card {
    padding: var(--space-3);
  }

  .outcome-record,
  .campaign-attempt-record {
    padding: var(--space-3);
  }

  .market-mobile-head h3 {
    margin: 0;
  }

  .market-mobile-head .eyebrow {
    margin-block-end: var(--space-1);
    font-size: 0.66rem;
  }

  .market-mobile-returns {
    margin-block: var(--space-2);
  }

  .market-mobile-summary {
    align-items: flex-start;
  }

  .market-mobile-summary p {
    display: grid;
    gap: var(--space-1);
  }

  .market-mobile-details .disclosure__summary,
  .market-mobile-overflow .disclosure__summary {
    display: none;
  }

  .calendar-event-card {
    padding: var(--space-3);
  }

  .calendar-context {
    grid-template-columns: minmax(0, 1.2fr) minmax(8rem, 0.8fr);
  }

  .calendar-event-details .disclosure__summary {
    font-size: 0.7rem;
  }

  .technical-grid,
  .definition-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .context-coverage__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .history-empty-state {
    grid-template-columns: minmax(0, 1fr);
  }

  .decision-thesis .narrative-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .decision-thesis > .narrative-grid > .narrative-card:nth-child(4) {
    grid-column: auto;
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
  .radar-inline-chart .chart-status,
  .radar-inline-chart .chart-x-label,
  .radar-inline-chart .chart-only-label {
    font-size: 26px;
  }

  .radar-inline-chart .chart-y-label {
    font-size: 24px;
  }

  .mobile-cards td,
  .mobile-cards th[scope="row"] {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--space-1);
  }
}

@media (max-width: 21.25rem) {
  .command-hero .hero-pulse {
    display: none;
  }

  .app-workspace > .topbar {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: var(--space-2);
    padding-inline: var(--space-3);
  }

  .topbar-heading {
    grid-column: 1;
    grid-row: 1;
  }

  .topbar-state {
    display: contents;
  }

  .generation-disclosure {
    align-self: center;
    grid-column: 2;
    grid-row: 1;
  }

  .trust-strip {
    grid-column: 1 / -1;
    grid-row: 2;
    flex-wrap: nowrap;
    gap: var(--space-1);
  }

  .trust-strip .status-badge {
    padding-inline: 0.45rem;
    font-size: 0.68rem;
  }

  .run-details-long,
  .brand > span:last-child {
    display: none;
  }

  .run-details-short {
    display: inline;
  }

  .app-rail {
    grid-template-columns: auto minmax(0, 1fr);
    padding-inline: var(--space-3);
  }

  .mobile-nav {
    justify-self: end;
  }

  .health-metrics .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-2);
  }

  .health-metrics .metric-card {
    min-height: 4.5rem;
    padding: var(--space-2);
  }

  .today-metrics .metric-card {
    padding: var(--space-2);
  }

  .today-metrics .metric-card--text strong {
    overflow-wrap: normal;
    font-size: 0.82rem;
    line-height: 1.15;
  }

  .attention-card__head {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--space-2);
  }

  .attention-card__scores .mini-score {
    padding: 0.35rem;
  }

  .attention-card__scores .mini-score span,
  .attention-card__scores .mini-score small {
    overflow-wrap: normal;
    font-size: 0.62rem;
  }

  .attention-card__footer .card-action {
    white-space: nowrap;
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
