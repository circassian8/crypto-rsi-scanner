"""Operator shell and Decision Radar product-surface styles."""

from __future__ import annotations


OPERATOR_CSS = r"""
/* Operator Experience V1 shell and product components. */
.app-shell {
  display: grid;
  min-height: 100vh;
  grid-template-columns: 15rem minmax(0, 1fr);
}

.app-rail {
  position: sticky;
  z-index: 20;
  inset-block-start: 0;
  display: flex;
  min-width: 0;
  height: 100vh;
  flex-direction: column;
  gap: var(--space-5);
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
  gap: var(--space-2);
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
  padding: var(--space-4) clamp(var(--space-4), 3vw, var(--space-6));
  border-block-end: 1px solid var(--color-border);
  background: rgb(7 11 20 / 0.9);
  backdrop-filter: blur(18px);
}

.app-workspace > main {
  width: min(100%, var(--content-max));
}

.topbar h1 {
  margin: 0;
  font-size: clamp(1.35rem, 2vw, 1.8rem);
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

.research-banner {
  margin-block: 0 var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid #31506a;
  border-radius: var(--radius-md);
  background: #0c2032;
  color: #ccefff;
}

.generation-disclosure {
  margin-block-end: var(--space-5);
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
  gap: var(--space-5);
  margin-block: var(--space-3) var(--space-5);
  padding: clamp(var(--space-5), 4vw, var(--space-7));
  overflow: hidden;
  border: 1px solid #25496a;
  border-radius: 1.25rem;
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
  width: 8rem;
  height: 8rem;
  flex: 0 0 auto;
  place-content: center;
  border: 1px solid #2c6b8f;
  border-radius: 50%;
  background: rgb(19 185 250 / 0.08);
  color: var(--color-accent);
  text-align: center;
}

.count-badge,
.hero-pulse span {
  font-size: 2.1rem;
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
  min-height: 7.5rem;
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
  font-size: clamp(1.45rem, 3vw, 2rem);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  overflow-wrap: anywhere;
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

.idea-grid,
.narrative-grid,
.chart-grid,
.two-column,
.mini-score-grid,
.filter-grid {
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
  padding: var(--space-5);
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: linear-gradient(155deg, #142039, #0d1628);
  box-shadow: var(--shadow-panel);
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
  font-size: 1.45rem;
}

.idea-card h3 a {
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
  min-height: 3.2rem;
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

.card-action {
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

.filter-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 10rem), 1fr));
}

.filter-grid label {
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

.score-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr));
}

.score-card {
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.score-card > div:first-child {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.score-card strong {
  font-size: 1.5rem;
  font-variant-numeric: tabular-nums;
}

.score-card strong small {
  color: var(--color-text-subtle);
  font-size: 0.7rem;
}

.score-card p {
  min-height: 2.8rem;
  color: var(--color-text-muted);
  font-size: 0.8rem;
}

.score-meter {
  height: 0.35rem;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-border);
}

.score-meter span {
  display: block;
  height: 100%;
  max-width: 100%;
  border-radius: inherit;
  background: currentColor;
}

.narrative-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
  margin-block: var(--space-5);
}

.narrative-card {
  margin: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-inline-start-width: 0.22rem;
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.narrative-card h2 {
  font-size: 1rem;
}

.narrative-card ul {
  margin: 0;
  padding-inline-start: 1.15rem;
}

.tone-positive { color: var(--color-positive); }
.tone-info { color: var(--color-info); }
.tone-warning { color: var(--color-warning); }
.tone-danger { color: var(--color-danger); }
.tone-muted { color: var(--color-text-subtle); }
.narrative-card.tone-positive { border-inline-start-color: var(--color-positive); color: var(--color-text); }
.narrative-card.tone-info { border-inline-start-color: var(--color-info); color: var(--color-text); }
.narrative-card.tone-warning { border-inline-start-color: var(--color-warning); color: var(--color-text); }
.narrative-card.tone-danger { border-inline-start-color: var(--color-danger); color: var(--color-text); }

.chart-grid {
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 24rem), 1fr));
}

.radar-inline-chart {
  min-height: 11rem;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.two-column {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
}

.calendar-mini,
.mover-row {
  align-items: center;
  padding-block: var(--space-3);
  border-block-end: 1px solid var(--color-border);
}

.calendar-mini:last-child,
.mover-row:last-child {
  border-block-end: 0;
}

.calendar-mini p,
.mover-row p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.78rem;
}

.mover-row small {
  display: block;
  color: var(--color-text-subtle);
}

.empty-inline {
  padding: var(--space-4);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  color: var(--color-text-muted);
}

.idea-hero h2 span {
  color: var(--color-text-subtle);
  font-size: 0.8em;
  font-weight: 500;
}

.idea-expiry {
  min-width: 10rem;
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: rgb(7 11 20 / 0.45);
  text-align: right;
}

.idea-expiry span {
  display: block;
  color: var(--color-text-muted);
  font-size: 0.72rem;
  text-transform: uppercase;
}

.copy-value {
  white-space: pre-wrap;
  word-break: break-word;
}

.technical-details {
  content-visibility: auto;
}

.number {
  font-variant-numeric: tabular-nums;
  font-weight: 720;
}

.anomaly-card {
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
}

.anomaly-card > strong {
  font-size: 1.5rem;
}
""".strip()


__all__ = ("OPERATOR_CSS",)
