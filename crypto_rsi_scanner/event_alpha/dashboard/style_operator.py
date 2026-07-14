"""Operator shell and Decision Radar product-surface styles."""

from __future__ import annotations


OPERATOR_CSS = r"""
/* Operator Experience V1 shell and product components. */
.app-shell {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 14rem minmax(0, 1fr);
}

.app-rail {
  position: sticky;
  z-index: 20;
  inset-block-start: 0;
  display: flex;
  min-width: 0;
  height: 100vh;
  flex-direction: column;
  gap: var(--space-6);
  padding: var(--space-5) var(--space-4);
  overflow-y: auto;
  border-inline-end: 1px solid var(--color-border);
  background: rgb(7 11 20 / 0.96);
  backdrop-filter: blur(16px);
}

.brand {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-3);
  color: var(--color-text);
  text-decoration: none;
}

.brand-mark {
  display: grid;
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid #247ba3;
  border-radius: 0.8rem;
  background: linear-gradient(145deg, #153c5a, #102336);
  color: #b9efff;
  font-weight: 900;
}

.brand strong,
.brand small {
  display: block;
}

.brand small,
.rail-safety {
  color: var(--color-text-subtle);
  font-size: 0.76rem;
}

.app-rail .primary-nav {
  display: grid;
  gap: var(--space-5);
}

.nav-group {
  display: grid;
  gap: var(--space-1);
}

.nav-group-label {
  margin: 0 0 var(--space-1);
  padding-inline: var(--space-3);
  color: var(--color-text-subtle);
  font-size: 0.67rem;
  font-weight: 800;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.app-rail .primary-nav a {
  justify-content: flex-start;
  border-color: transparent;
  background: transparent;
  color: var(--color-text-muted);
}

.app-rail .primary-nav a:hover,
.app-rail .primary-nav a[aria-current="page"] {
  border-color: var(--color-border);
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.rail-safety {
  margin-block: auto 0;
  padding-block-start: var(--space-4);
  border-block-start: 1px solid var(--color-border);
  line-height: 1.7;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.mobile-nav {
  display: none;
}

.app-workspace {
  min-width: 0;
}

.app-workspace > .topbar {
  position: sticky;
  z-index: 15;
  inset-block-start: 0;
  width: 100%;
  max-width: none;
  margin: 0;
  min-height: 5rem;
  padding: var(--space-3) clamp(var(--space-4), 3vw, var(--space-6));
  border-block-end: 1px solid var(--color-border);
  background: rgb(7 11 20 / 0.9);
  backdrop-filter: blur(18px);
}

.app-workspace > main {
  width: min(100%, var(--content-max));
}

.topbar h1 {
  margin: 0;
  font-size: clamp(1.3rem, 1.8vw, 1.65rem);
}

.topbar .eyebrow {
  margin-block-end: 0.15rem;
}

.topbar-heading {
  display: grid;
  min-width: 0;
  grid-template-columns: auto auto;
  align-items: baseline;
  gap: 0 var(--space-3);
}

.topbar-heading .eyebrow {
  grid-column: 1 / -1;
}

.topbar-safety {
  margin: 0;
  color: var(--color-text-subtle);
  font-size: 0.76rem;
}

.topbar-state {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-3);
}

.trust-strip,
.chip-row,
.badge-row,
.active-filters,
.filter-actions,
.hero-actions {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.trust-strip .status-badge {
  min-height: 1.55rem;
  padding-block: 0.1rem;
  font-size: 0.7rem;
  letter-spacing: 0.025em;
}

.generation-disclosure {
  position: relative;
  flex: 0 0 auto;
}

.run-details-short {
  display: none;
}

.generation-disclosure > summary {
  min-height: var(--touch-target);
  padding: var(--space-2) var(--space-3);
  cursor: pointer;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 750;
  list-style-position: inside;
}

.generation-disclosure[open] > summary {
  border-color: var(--color-border-strong);
  background: var(--color-surface-raised);
  color: var(--color-text);
}

.generation-popover {
  position: absolute;
  z-index: 50;
  inset-block-start: calc(100% + var(--space-2));
  inset-inline-end: 0;
  width: min(38rem, calc(100vw - 3rem));
  padding: var(--space-4);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-canvas-raised);
  box-shadow: 0 20px 55px rgb(0 0 0 / 0.45);
}

.generation-summary,
.run-safety {
  margin-block-end: var(--space-3);
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.run-status-badges {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-block-end: var(--space-3);
}

.technical-grid,
.definition-grid {
  display: grid;
  grid-template-columns: minmax(9rem, 14rem) minmax(0, 1fr);
  gap: var(--space-2) var(--space-4);
}

.page-intro,
.command-hero,
.idea-hero {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-block: 0 var(--space-4);
  padding: clamp(var(--space-4), 2.5vw, var(--space-6));
  overflow: hidden;
  border: 1px solid #25496a;
  border-radius: var(--radius-lg);
  background:
    radial-gradient(circle at 100% 0, rgb(103 212 255 / 0.16), transparent 24rem),
    linear-gradient(145deg, #101d31, #0c1424);
  box-shadow: var(--shadow-panel);
}

.page-intro > div:first-child,
.command-hero > div:first-child {
  max-width: 52rem;
}

.page-intro p,
.command-hero p {
  max-width: 48rem;
  color: var(--color-text-muted);
}

.count-badge,
.hero-pulse {
  display: grid;
  width: auto;
  min-width: 6rem;
  height: auto;
  min-height: 4.5rem;
  flex: 0 0 auto;
  place-content: center;
  border: 1px solid #2c6b8f;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: rgb(19 185 250 / 0.055);
  color: var(--color-accent);
  text-align: center;
}

.count-badge,
.hero-pulse span {
  font-size: 1.65rem;
  font-weight: 900;
}

.count-badge small,
.hero-pulse small {
  display: block;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.metric-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
}

.metric-card {
  display: grid;
  min-width: 0;
  min-height: 6rem;
  align-content: space-between;
  gap: var(--space-2);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: linear-gradient(145deg, var(--color-surface), var(--color-surface-soft));
}

.metric-card span,
.metric-card small {
  color: var(--color-text-muted);
}

.metric-card strong {
  font-size: clamp(1.125rem, 1.75vw, 1.4rem);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  overflow-wrap: break-word;
  word-break: normal;
}

.layer-funnel {
  display: grid;
  min-width: 0;
  align-items: stretch;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr);
  gap: var(--space-2);
}

.funnel-step {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
}

.funnel-step span,
.funnel-step small {
  color: var(--color-text-muted);
}

.funnel-step strong {
  color: var(--color-accent);
  font-size: 1.75rem;
  font-variant-numeric: tabular-nums;
}

.funnel-arrow {
  align-self: center;
  color: var(--color-text-muted);
  font-size: 1.25rem;
}

.funnel-interpretation {
  margin-block: var(--space-4) 0;
  color: var(--color-text-muted);
}

.section-heading,
.idea-card-head,
.calendar-mini,
.mover-row,
.warning-row {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.section-heading {
  margin-block-end: var(--space-4);
}

.section-heading p,
.section-heading h2 {
  margin-block-end: var(--space-2);
}

.section-heading > a,
.diagnostic-link > a,
.anomaly-card__decision > a,
.market-mobile-summary a {
  display: inline-flex;
  min-height: 1.5rem;
  align-items: center;
}

.lane-count {
  display: grid;
  min-width: 2.25rem;
  height: 2.25rem;
  place-content: center;
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  font-weight: 850;
}

.alert {
  display: flex;
  min-width: 0;
  gap: var(--space-4);
  margin-block: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.alert h2 {
  font-size: 1rem;
}

.alert-icon {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  place-content: center;
  border: 1px solid currentColor;
  border-radius: 50%;
  font-weight: 900;
}

.alert-positive { border-color: #277f63; background: var(--color-positive-bg); color: #c5ffe7; }
.alert-info { border-color: #2e6597; background: var(--color-info-bg); color: #d2eaff; }
.alert-warning { border-color: #83651a; background: var(--color-warning-bg); color: #fff0bd; }
.alert-danger { border-color: #99424b; background: var(--color-danger-bg); color: #ffd7db; }

.warning-stack {
  padding: 0;
  overflow: hidden;
}

.warning-stack > .section-heading {
  padding: var(--space-5) var(--space-5) 0;
}

.warning-row {
  min-height: var(--touch-target);
  align-items: center;
  padding: var(--space-3) var(--space-5);
  border-block-start: 1px solid var(--color-border);
  color: var(--color-text);
  text-decoration: none;
}

.warning-row:hover {
  background: rgb(255 209 102 / 0.05);
}

.warning-row p {
  margin: 0;
  color: var(--color-text-muted);
}

.attention-lane {
  margin-block: var(--space-6);
}

.attention-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr));
  gap: var(--space-3);
}

.attention-card {
  position: relative;
  display: grid;
  min-width: 0;
  gap: var(--space-3);
  padding: var(--space-4);
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.attention-card::before {
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  width: 0.22rem;
  background: var(--color-info);
  content: "";
}

.attention-card.route-high_confidence_watch::before { background: var(--color-positive); }
.attention-card.route-actionable_watch::before { background: #7cd4ff; }
.attention-card.route-rapid_market_anomaly::before { background: var(--color-warning); }
.attention-card.route-risk_watch::before,
.attention-card.route-fade_exhaustion_review::before { background: var(--color-danger); }

.attention-card__head,
.attention-card__footer {
  display: flex;
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.attention-card__head h3 {
  font-size: 1.2rem;
}

.attention-card__head h3 a {
  display: inline-flex;
  min-height: 1.5rem;
  align-items: center;
  color: var(--color-text);
  text-decoration: none;
}

.attention-card__head .status-badge {
  flex: 0 0 auto;
  overflow-wrap: normal;
  white-space: nowrap;
}

.attention-card__scores {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.attention-card__thesis {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--color-text-muted);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.attention-card__footer {
  align-items: flex-end;
  padding-block-start: var(--space-2);
  border-block-start: 1px solid var(--color-border);
}

.attention-card__footer > span {
  display: grid;
  gap: 0.12rem;
  color: var(--color-text-muted);
}

.attention-card__footer small {
  color: var(--color-text-subtle);
  font-size: 0.65rem;
  font-weight: 750;
  letter-spacing: 0.035em;
  text-transform: uppercase;
}

.lane-overflow-link {
  margin-block: var(--space-3) 0;
  text-align: end;
}

.today-metrics {
  margin-block: var(--space-5);
}

.idea-grid,
.narrative-grid,
.chart-grid,
.two-column,
.mini-score-grid,
.filter-grid,
.filter-grid-primary,
.filter-grid-advanced {
  display: grid;
  min-width: 0;
  gap: var(--space-4);
}

.idea-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr));
}

.idea-card {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  box-shadow: none;
}

.idea-card:hover,
.idea-card:focus-within {
  border-color: var(--color-border-strong);
  background: var(--color-surface-raised);
}

.idea-card::before {
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  width: 0.22rem;
  background: var(--color-info);
  content: "";
}

.idea-card.route-high_confidence_watch::before { background: var(--color-positive); }
.idea-card.route-actionable_watch::before { background: #7cd4ff; }
.idea-card.route-rapid_market_anomaly::before { background: var(--color-warning); }
.idea-card.route-risk_watch::before,
.idea-card.route-fade_exhaustion_review::before { background: var(--color-danger); }

.idea-card h3 {
  font-size: 1.25rem;
}

.idea-card h3 a {
  display: inline-flex;
  min-height: 1.5rem;
  align-items: center;
  color: var(--color-text);
  text-decoration: none;
}

.idea-card .muted {
  margin: 0;
}

.mini-score-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-2);
}

.mini-score {
  display: grid;
  min-width: 0;
  gap: 0.15rem;
  padding: var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-soft);
}

.mini-score span,
.mini-score small {
  color: var(--color-text-muted);
  font-size: 0.68rem;
}

.mini-score strong {
  font-size: 1.1rem;
  font-variant-numeric: tabular-nums;
}

.idea-why {
  min-height: 2.6rem;
  color: var(--color-text-muted);
}

.idea-meta {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
  flex-wrap: wrap;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.idea-meta small {
  margin-inline-end: var(--space-1);
  color: var(--color-text-subtle);
  font-size: 0.66rem;
  font-weight: 750;
  letter-spacing: 0.035em;
  text-transform: uppercase;
}

.idea-meta > *:not(:last-child)::after {
  padding-inline-start: var(--space-2);
  color: var(--color-border-strong);
  content: "·";
}

.card-warning,
.sample-warning {
  padding: var(--space-3);
  border-inline-start: 0.2rem solid var(--color-warning);
  border-radius: var(--radius-sm);
  background: rgb(255 209 102 / 0.07);
  color: #ffe9a6;
}

.sample-note {
  margin-block: var(--space-3) 0;
  padding-block-start: var(--space-3);
  border-block-start: 1px solid var(--color-border);
  color: var(--color-text-muted);
}

.card-action {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  margin-block-start: auto;
  font-weight: 780;
}

.filter-panel {
  margin-block: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.idea-filter-disclosure,
.calendar-filter-disclosure {
  margin-block: var(--space-4);
  padding-inline: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.idea-filter-disclosure > summary,
.calendar-filter-disclosure > summary {
  justify-content: space-between;
  gap: var(--space-3);
}

.embedded-filter-panel {
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.filter-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
}

.filter-grid-primary {
  grid-template-columns: minmax(16rem, 2fr) minmax(10rem, 1fr);
}

.filter-grid-advanced {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
}

.filter-grid label,
.filter-grid-primary label,
.filter-grid-advanced label {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 700;
}

.filter-search {
  grid-column: span 2;
}

.filter-actions {
  margin-block-start: var(--space-4);
}

.filter-advanced {
  margin-block-start: var(--space-3);
}

.filter-advanced > summary,
.comparison-panel > summary,
.market-explanation > summary,
.market-mobile-overflow > summary {
  justify-content: space-between;
  gap: var(--space-3);
}

.filter-advanced .filter-grid {
  padding-block-start: var(--space-3);
}

.button-primary {
  border-color: #247ba3;
  background: #124361;
  color: #e6f8ff;
}

.button-quiet {
  background: transparent;
}

.active-filters {
  margin-block: var(--space-3);
}

.filter-chip {
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-soft);
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.comparison-panel,
.market-table {
  font-size: 0.83rem;
}

.market-table th,
.market-table td {
  white-space: nowrap;
}

.market-table th:first-child,
.market-table td:first-child,
.market-table th:last-child,
.market-table td:last-child {
  white-space: normal;
}

.market-table th:first-child,
.market-table td:first-child {
  min-width: 8.5rem;
}

.market-table th:last-child,
.market-table td:last-child {
  min-width: 8rem;
}

.market-table th:nth-child(2),
.market-table td:nth-child(2) {
  min-width: 10rem;
  white-space: normal;
  text-align: left;
}

.market-table td:nth-child(n + 3):nth-child(-n + 7) {
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.market-row-details {
  display: inline-block;
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  font-weight: 500;
}

.market-asset-heading {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.market-row-details summary {
  width: fit-content;
  min-height: 1.5rem;
  cursor: pointer;
  color: var(--color-accent);
  font-weight: 750;
}

.market-row-details dl {
  display: grid;
  min-width: 14rem;
  grid-template-columns: minmax(5rem, auto) minmax(0, 1fr);
  gap: var(--space-1) var(--space-2);
  margin-block: var(--space-2) 0;
}

.market-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: var(--space-3);
}

.market-filters > .filter-grid {
  grid-column: 1;
  grid-row: 1;
}

.market-filters > .filter-actions {
  grid-column: 2;
  grid-row: 1;
  margin: 0;
}

.market-filters > .filter-advanced {
  grid-column: 1 / -1;
}

.market-row-details dt,
.market-row-details dd {
  margin: 0;
}

.market-mobile-list {
  display: none;
}

.calendar-coverage--verified {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--space-2);
  padding-block: var(--space-3);
}

.calendar-coverage__heading {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.calendar-coverage__heading h2,
.calendar-coverage__heading .eyebrow,
.calendar-coverage__receipt {
  margin: 0;
}

.calendar-coverage__receipt {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.calendar-coverage__receipt strong {
  color: var(--color-text);
}

.calendar-coverage--verified > .disclosure {
  margin-block-start: var(--space-1);
}

.market-mobile-items {
  display: grid;
  gap: var(--space-3);
}

.market-mobile-card {
  margin: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
}

.market-mobile-head,
.market-mobile-returns,
.market-mobile-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.market-mobile-head p,
.market-mobile-summary p {
  margin: 0;
}

.market-mobile-head .status-badge {
  flex: 0 0 auto;
  overflow-wrap: normal;
  white-space: nowrap;
}

.market-mobile-returns {
  margin-block: var(--space-3);
  padding-block: var(--space-2);
  border-block: 1px solid var(--color-border);
}

.market-mobile-returns > span {
  display: grid;
  gap: 0.15rem;
}

.market-mobile-returns small {
  color: var(--color-text-subtle);
}

.market-mobile-card details {
  margin-block-start: var(--space-3);
  border-block-start: 1px solid var(--color-border);
}

.market-mobile-card details summary {
  min-height: var(--touch-target);
  padding-block: var(--space-2);
  cursor: pointer;
  color: var(--color-accent);
  font-weight: 750;
}

.market-mobile-overflow {
  margin-block-start: var(--space-3);
}

.health-action {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-inline-start-width: 0.22rem;
  border-radius: var(--radius-sm);
  color: var(--color-text);
  text-decoration: none;
}

.health-action[data-tone="danger"] { border-inline-start-color: var(--color-danger); }
.health-action[data-tone="warning"] { border-inline-start-color: var(--color-warning); }
.health-action[data-tone="positive"] { border-inline-start-color: var(--color-positive); }
.health-action[data-tone="muted"] { border-inline-start-color: var(--color-text-subtle); }

.health-action:hover,
.health-action:focus-visible {
  border-color: var(--color-border-strong);
  background: var(--color-surface-soft);
}

.health-action p {
  margin: 0;
  color: var(--color-text-muted);
}

.health-action__icon {
  display: grid;
  width: 1.75rem;
  height: 1.75rem;
  place-items: center;
  border-radius: 50%;
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
  font-weight: 850;
}

.health-action[data-tone="danger"] .health-action__icon {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.health-action[data-tone="warning"] .health-action__icon {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.health-action[data-tone="positive"] .health-action__icon {
  background: var(--color-positive-bg);
  color: var(--color-positive);
}

.health-action__copy {
  display: grid;
  min-width: 0;
  gap: var(--space-1);
}

.health-action__arrow {
  color: var(--color-accent);
  font-size: 1.15rem;
}

.health-action-overflow {
  margin-block-start: var(--space-3);
}

.health-action-overflow > summary {
  color: var(--color-accent);
}

.responsive-table td small,
.responsive-table th small {
  display: block;
  margin-block-start: 0.2rem;
  color: var(--color-text-subtle);
}

.status-badge.tone-positive,
.mini-score.tone-positive { border-color: #277f63; color: var(--color-positive); }
.status-badge.tone-info,
.mini-score.tone-info { border-color: #2e6597; color: var(--color-info); }
.status-badge.tone-warning,
.mini-score.tone-warning { border-color: #83651a; color: var(--color-warning); }
.status-badge.tone-danger,
.mini-score.tone-danger { border-color: #99424b; color: var(--color-danger); }
.status-badge i {
  width: 0.38rem;
  height: 0.38rem;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
}

""".strip()


__all__ = ("OPERATOR_CSS",)
