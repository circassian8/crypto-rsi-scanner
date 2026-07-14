"""Outcome, campaign, and anomaly record styles."""

from __future__ import annotations


RECORDS_CSS = r"""
.outcome-mobile-list,
.campaign-mobile-list {
  display: none;
}

.table-stack-cell,
.table-identity-cell {
  display: grid;
  min-width: 0;
  gap: 0.18rem;
}

.table-stack-cell strong,
.table-identity-cell strong,
.table-stack-cell small,
.table-identity-cell small {
  white-space: nowrap;
}

.table-stack-cell small,
.table-identity-cell small,
.table-cohort-cell small {
  color: var(--color-text-subtle);
  font-size: 0.66rem;
  font-weight: 720;
  letter-spacing: 0.025em;
}

.table-identity-cell {
  min-width: 10rem;
}

.table-identity-cell small {
  max-width: 15rem;
  overflow: hidden;
  text-overflow: ellipsis;
}

.table-cohort-cell {
  display: flex;
  min-width: 14rem;
  align-items: baseline;
  gap: var(--space-3);
  white-space: nowrap;
}

.table-cohort-cell > span {
  display: inline-flex;
  align-items: baseline;
  gap: 0.28rem;
}

.table-cohort-cell strong {
  color: var(--color-text);
  font-size: 0.78rem;
}

.outcome-desktop-table .data-table th:nth-child(1),
.outcome-desktop-table .data-table td:nth-child(1),
.outcome-desktop-table .data-table th:nth-child(2),
.outcome-desktop-table .data-table td:nth-child(2),
.outcome-desktop-table .data-table th:nth-child(3),
.outcome-desktop-table .data-table td:nth-child(3),
.outcome-desktop-table .data-table th:nth-child(6),
.outcome-desktop-table .data-table td:nth-child(6) {
  min-width: max-content;
  overflow-wrap: normal;
  white-space: nowrap;
}

.campaign-desktop-table .data-table th:nth-child(3),
.campaign-desktop-table .data-table td:nth-child(3),
.campaign-desktop-table .data-table th:nth-child(4),
.campaign-desktop-table .data-table td:nth-child(4),
.campaign-desktop-table .data-table th:nth-child(5),
.campaign-desktop-table .data-table td:nth-child(5) {
  min-width: max-content;
  overflow-wrap: normal;
  white-space: nowrap;
}

.campaign-desktop-table .status-badge {
  max-width: none;
  overflow-wrap: normal;
  white-space: nowrap;
}

.outcome-record,
.campaign-attempt-record {
  min-width: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
}

.outcome-record__header,
.campaign-attempt-record__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.outcome-record__header h3,
.campaign-attempt-record__header h3 {
  margin: 0;
}

.outcome-record__scores {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
  margin-block: var(--space-3);
}

.outcome-record__scores span {
  display: grid;
  gap: 0.15rem;
  padding: var(--space-2);
  border-inline-start: 2px solid var(--color-border-strong);
}

.outcome-record__scores small,
.campaign-attempt-record__facts small {
  color: var(--color-text-subtle);
  font-size: 0.66rem;
  font-weight: 750;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.outcome-record__scores strong {
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}

.outcome-record__timing,
.outcome-record__result,
.campaign-attempt-record__summary {
  margin-block: var(--space-2);
  color: var(--color-text-muted);
  font-size: 0.82rem;
}

.outcome-record__details,
.campaign-attempt-record__details {
  margin-block-start: var(--space-3);
}

.campaign-attempt-record__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
  margin-block: var(--space-3);
}

.campaign-attempt-record__facts span {
  display: grid;
  gap: var(--space-1);
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: rgb(7 11 20 / 0.36);
}

.copy-value {
  white-space: pre-wrap;
  word-break: break-word;
}

.technical-details {
  content-visibility: visible;
}

.technical-details > summary {
  min-height: var(--touch-target);
  cursor: pointer;
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

.anomaly-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.anomaly-card__metric {
  display: grid;
  flex: 0 0 auto;
  gap: var(--space-1);
  text-align: end;
}

.anomaly-card__metrics {
  display: flex;
  flex: 0 0 auto;
  align-items: flex-start;
  gap: var(--space-5);
}

.anomaly-card__metric span,
.anomaly-card__decision > span {
  color: var(--color-text-subtle);
  font-size: 0.7rem;
  font-weight: 760;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.anomaly-card__metric strong {
  font-size: 1.5rem;
}

.anomaly-card__metric--secondary strong {
  color: var(--color-text-muted);
  font-size: 1rem;
}

.anomaly-card__decision {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-block: var(--space-3);
  padding-block: var(--space-3);
  border-block: 1px solid var(--color-border);
}

.anomaly-card__decision small {
  color: var(--color-text-subtle);
}
""".strip()


__all__ = ("RECORDS_CSS",)
