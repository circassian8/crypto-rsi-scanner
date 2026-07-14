"""Decision detail, context, history, and compact calendar styles."""

from __future__ import annotations


DECISION_DETAIL_CSS = r"""
.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr));
  gap: var(--space-3);
  margin-block: var(--space-4);
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
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

.decision-thesis .narrative-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-block: 0;
}

.decision-thesis > .narrative-grid > .narrative-card:nth-child(4) {
  grid-column: 1 / -1;
}

.thesis-notes,
.data-provenance,
.context-coverage {
  margin-block-start: var(--space-4);
}

.thesis-notes > summary,
.context-coverage > summary {
  justify-content: space-between;
  gap: var(--space-3);
}

.context-coverage__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.context-coverage__section {
  margin: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
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
  grid-template-columns: minmax(0, 1fr);
}

.radar-inline-chart {
  min-height: 11rem;
  overflow: hidden;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
}

.radar-inline-chart .chart-status,
.radar-inline-chart .chart-x-label,
.radar-inline-chart .chart-only-label {
  font-size: 13px;
}

.radar-inline-chart .chart-y-label {
  font-size: 11px;
}

.history-empty-state {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(12rem, 0.9fr) minmax(0, 1.1fr);
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
}

.history-empty-state--partial {
  grid-column: 1 / -1;
}

.history-empty-state h3,
.history-empty-state p {
  margin: 0;
}

.history-empty-state h3 {
  margin-block-end: var(--space-1);
  font-size: 1rem;
}

.history-empty-state p:not(.eyebrow) {
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.history-empty-series {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.history-empty-series li {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: 0.72rem;
  line-height: 1.25;
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

.calendar-mini .status-badge {
  max-width: none;
  overflow-wrap: normal;
  white-space: nowrap;
}

.calendar-event-card {
  margin: 0;
  padding: var(--space-4);
  background: var(--color-surface);
}

.calendar-event-card--high-impact {
  border-inline-start: 0.22rem solid var(--color-warning);
}

.calendar-event-card__header .badge-row {
  justify-content: flex-start;
}

.calendar-event-card__header h3 {
  margin-block: var(--space-2) var(--space-1);
  font-size: 1.15rem;
}

.calendar-event-meta,
.calendar-event-time {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.calendar-event-meta {
  margin-block-start: var(--space-2);
}

.time-note {
  margin-inline-start: var(--space-2);
  color: var(--color-text-subtle);
  font-size: 0.72rem;
}

.calendar-event-time .countdown {
  margin-inline-start: var(--space-2);
}

.calendar-context {
  grid-template-columns: minmax(0, 1.35fr) minmax(10rem, 0.65fr);
  gap: var(--space-3);
  margin-block-start: var(--space-3);
}

.calendar-context h4,
.calendar-context p {
  margin-block-end: var(--space-2);
}

.calendar-event-details {
  margin-block-start: var(--space-2);
}

.calendar-event-details > summary {
  justify-content: space-between;
  gap: var(--space-3);
}

.calendar-detail-section {
  margin: 0;
  padding: var(--space-3) 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.calendar-detail-section + .calendar-detail-section {
  border-block-start: 1px solid var(--color-border);
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
""".strip()


__all__ = ("DECISION_DETAIL_CSS",)
