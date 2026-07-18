"""Operator work queue, health-action, and status presentation styles."""

from __future__ import annotations


OPERATOR_WORK_CSS = r"""
.operator-work-panel {
  border-color: #6b5724;
  background:
    radial-gradient(circle at 100% 0, rgb(242 189 76 / 0.09), transparent 22rem),
    var(--color-surface);
}

.operator-work-intro,
.operator-work-source {
  color: var(--color-text-muted);
}

.operator-work-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
  gap: var(--space-3);
  margin-block-start: var(--space-4);
}

.operator-work-card {
  display: flex;
  min-width: 0;
  min-height: 17rem;
  flex-direction: column;
  gap: var(--space-3);
  margin: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-block-start: 0.22rem solid var(--color-warning);
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
}

.operator-work-card h3,
.operator-work-card p {
  margin: 0;
}

.operator-work-card > p:not(.eyebrow) {
  color: var(--color-text-muted);
}

.operator-work-card .button {
  align-self: flex-start;
  margin-block-start: auto;
}

.operator-work-command {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
}

.operator-work-command span {
  color: var(--color-text-subtle);
  font-size: 0.7rem;
  font-weight: 800;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}

.operator-work-command code {
  overflow-wrap: anywhere;
  color: var(--color-accent);
  white-space: normal;
}

.operator-work-source {
  margin-block: var(--space-4) 0;
  font-size: 0.78rem;
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


__all__ = ("OPERATOR_WORK_CSS",)
