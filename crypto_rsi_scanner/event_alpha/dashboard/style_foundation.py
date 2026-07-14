"""Foundation tokens and shared dashboard component styles."""

from __future__ import annotations


FOUNDATION_CSS = r"""
:root {
  color-scheme: dark;
  --color-canvas: #070b14;
  --color-canvas-raised: #0b1120;
  --color-surface: #111a2d;
  --color-surface-raised: #17233a;
  --color-surface-soft: #0d1628;
  --color-text: #f4f7ff;
  --color-text-muted: #aebbd2;
  --color-text-subtle: #7f8da7;
  --color-border: #2a3955;
  --color-border-strong: #425675;
  --color-accent: #67d4ff;
  --color-accent-strong: #13b9fa;
  --color-positive: #5ee6a8;
  --color-positive-bg: #0b392d;
  --color-info: #78baff;
  --color-info-bg: #102f52;
  --color-warning: #ffd166;
  --color-warning-bg: #432f08;
  --color-danger: #ff8a94;
  --color-danger-bg: #45151d;
  --color-neutral: #c8d2e4;
  --color-neutral-bg: #253249;
  --focus-ring: #a5e8ff;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.5rem;
  --space-6: 2rem;
  --space-7: 3rem;
  --radius-sm: 0.45rem;
  --radius-md: 0.75rem;
  --radius-lg: 1rem;
  --shadow-panel: 0 18px 45px rgb(0 0 0 / 0.2);
  --content-max: 90rem;
  --touch-target: 2.75rem;
  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

html {
  min-width: 20rem;
  background: var(--color-canvas);
  scroll-behavior: smooth;
}

body {
  min-width: 0;
  min-height: 100vh;
  margin: 0;
  background:
    radial-gradient(circle at 10% -10%, rgb(19 185 250 / 0.12), transparent 32rem),
    var(--color-canvas);
  color: var(--color-text);
  font: 0.9375rem/1.55 var(--font-sans);
  text-rendering: optimizeLegibility;
}

body,
main,
header,
nav,
section,
article,
aside,
div,
form,
fieldset,
dl,
table {
  min-width: 0;
}

img,
svg,
canvas {
  max-width: 100%;
}

h1,
h2,
h3,
h4,
p {
  overflow-wrap: anywhere;
}

h1,
h2,
h3,
h4 {
  margin: 0 0 var(--space-3);
  line-height: 1.18;
  letter-spacing: -0.018em;
}

h1 { font-size: clamp(1.55rem, 3vw, 2.25rem); }
h2 { font-size: clamp(1.3rem, 2.4vw, 1.75rem); }
h3 { font-size: clamp(1.05rem, 1.8vw, 1.3rem); }
h4 { font-size: 1rem; }

p {
  margin: 0 0 var(--space-4);
}

a {
  color: var(--color-accent);
  text-underline-offset: 0.16em;
  text-decoration-thickness: 0.08em;
}

a:hover {
  color: #b4ebff;
}

:focus-visible {
  outline: 0.2rem solid var(--focus-ring);
  outline-offset: 0.18rem;
  border-radius: var(--radius-sm);
}

.skip-link {
  position: fixed;
  z-index: 1000;
  inset-block-start: var(--space-2);
  inset-inline-start: var(--space-2);
  padding: var(--space-3) var(--space-4);
  transform: translateY(-180%);
  border-radius: var(--radius-sm);
  background: var(--color-text);
  color: var(--color-canvas);
  font-weight: 800;
}

.skip-link:focus {
  transform: translateY(0);
}

.visually-hidden,
.sr-only {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  padding: 0 !important;
  margin: -1px !important;
  overflow: hidden !important;
  clip: rect(0, 0, 0, 0) !important;
  white-space: nowrap !important;
  border: 0 !important;
}

header,
main,
.site-header,
.app-main {
  width: min(100%, var(--content-max));
  margin-inline: auto;
  padding-inline: clamp(var(--space-4), 3vw, var(--space-6));
}

header,
.site-header {
  padding-block: var(--space-5) var(--space-3);
}

main,
.app-main {
  padding-block: var(--space-3) var(--space-7);
}

.topbar,
.page-header,
.cluster {
  display: flex;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}

nav,
.primary-nav {
  display: flex;
  min-width: 0;
  gap: var(--space-2);
  flex-wrap: wrap;
}

nav a,
.primary-nav a,
.button,
button {
  display: inline-flex;
  min-height: var(--touch-target);
  align-items: center;
  justify-content: center;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-soft);
  color: var(--color-text);
  font-weight: 680;
  line-height: 1.2;
  text-decoration: none;
}

nav a:hover,
.primary-nav a:hover,
.primary-nav a[aria-current="page"],
nav a[aria-current="page"] {
  border-color: var(--color-accent-strong);
  background: #123653;
  color: #d7f5ff;
}

.stack {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-4);
}

.grid,
.metric-grid,
.card-grid {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
  gap: var(--space-4);
}

.panel,
.card,
section,
.banner,
.scope,
.authority-untrusted {
  min-width: 0;
  margin-block: var(--space-4);
  padding: clamp(var(--space-4), 2.2vw, var(--space-5));
  overflow-wrap: anywhere;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: linear-gradient(145deg, var(--color-surface), var(--color-surface-soft));
  box-shadow: var(--shadow-panel);
}

.card,
.metric {
  margin: 0;
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.eyebrow {
  margin: 0 0 var(--space-2);
  color: var(--color-accent);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.muted,
.scope,
.helper-text {
  color: var(--color-text-muted);
}

.unavailable {
  color: var(--color-text-subtle);
  font-style: italic;
}

.banner {
  border-color: #735d1f;
  background: var(--color-warning-bg);
  color: #ffe8a6;
}

.authority-untrusted {
  border: 0.18rem solid var(--color-danger);
  background: var(--color-danger-bg);
  color: #ffd7db;
}

.status-badge,
.badge,
.chip {
  display: inline-flex;
  max-width: 100%;
  min-height: 1.75rem;
  align-items: center;
  gap: var(--space-1);
  padding: 0.15rem 0.55rem;
  overflow-wrap: anywhere;
  border: 1px solid var(--color-border-strong);
  border-radius: 999px;
  background: var(--color-neutral-bg);
  color: var(--color-neutral);
  font-size: 0.79rem;
  font-weight: 780;
  line-height: 1.2;
}

.status-badge--positive,
.chip--positive,
.badge-current {
  border-color: #277f63;
  background: var(--color-positive-bg);
  color: var(--color-positive);
}

.status-badge--info,
.chip--info,
.badge-live {
  border-color: #2e6597;
  background: var(--color-info-bg);
  color: var(--color-info);
}

.status-badge--warning,
.chip--warning,
.badge-fixture {
  border-color: #83651a;
  background: var(--color-warning-bg);
  color: var(--color-warning);
}

.status-badge--danger,
.chip--danger,
.badge-stale {
  border-color: #99424b;
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.status-badge--muted,
.chip--muted {
  opacity: 0.82;
}

.chip-list {
  display: flex;
  min-width: 0;
  margin: 0;
  padding: 0;
  gap: var(--space-2);
  flex-wrap: wrap;
  list-style: none;
}

.score {
  display: inline-grid;
  min-width: 5.4rem;
  grid-template-columns: auto auto;
  align-items: baseline;
  gap: 0 var(--space-1);
  color: var(--color-neutral);
}

.score-value {
  font-size: 1.05rem;
  font-variant-numeric: tabular-nums;
  font-weight: 850;
}

.score-denominator {
  color: var(--color-text-subtle);
  font-size: 0.72rem;
}

.score-band {
  grid-column: 1 / -1;
  color: currentColor;
  font-size: 0.72rem;
  font-weight: 720;
}

.score--positive { color: var(--color-positive); }
.score--info { color: var(--color-info); }
.score--warning { color: var(--color-warning); }
.score--danger { color: var(--color-danger); }
.score--muted { color: var(--color-text-subtle); }

.timestamp {
  font-variant-numeric: tabular-nums;
  text-decoration: underline dotted var(--color-border-strong);
  text-underline-offset: 0.2em;
}

.definition-list,
dl {
  display: grid;
  min-width: 0;
  grid-template-columns: minmax(9rem, 15rem) minmax(0, 1fr);
  margin: 0;
  gap: var(--space-2) var(--space-4);
}

.definition-list dt,
dt {
  color: var(--color-text-muted);
  font-weight: 650;
}

.definition-list dd,
dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.table-scroll {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  overscroll-behavior-inline: contain;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  scrollbar-color: var(--color-border-strong) var(--color-surface-soft);
}

.table-scroll:focus-visible {
  outline-offset: 0.1rem;
}

.data-table,
table {
  width: 100%;
  min-width: 48rem;
  border-collapse: collapse;
  border-spacing: 0;
  font-variant-numeric: tabular-nums;
}

.data-table caption,
table caption {
  padding: var(--space-3) var(--space-4);
  color: var(--color-text);
  font-weight: 760;
  text-align: left;
}

.data-table th,
.data-table td,
table th,
table td {
  min-width: 0;
  padding: 0.72rem var(--space-3);
  overflow-wrap: anywhere;
  word-break: normal;
  border-block-end: 1px solid var(--color-border);
  text-align: left;
  vertical-align: top;
}

.data-table thead th,
table thead th {
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.035em;
  text-transform: uppercase;
}

.data-table tbody th[scope="row"] {
  color: var(--color-text);
  font-weight: 760;
}

.data-table tbody tr:hover {
  background: rgb(103 212 255 / 0.045);
}

.data-table--compact th,
.data-table--compact td {
  padding-block: var(--space-2);
}

.candidate-filters,
.filter-bar {
  display: flex;
  min-width: 0;
  align-items: end;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-block: var(--space-4);
  padding: var(--space-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.candidate-filters label,
.filter-bar label {
  display: grid;
  min-width: min(100%, 10rem);
  gap: var(--space-1);
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 650;
}

button,
input,
select,
textarea {
  min-height: var(--touch-target);
  max-width: 100%;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  background: var(--color-canvas-raised);
  color: var(--color-text);
  font: inherit;
}

input,
select,
textarea {
  padding: var(--space-2) var(--space-3);
}

button {
  cursor: pointer;
}

.empty-state {
  display: grid;
  min-height: 9rem;
  place-content: center;
  padding: var(--space-5);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-md);
  background: var(--color-surface-soft);
  color: var(--color-text-muted);
  text-align: center;
}

.empty-state__title {
  margin: 0 0 var(--space-2);
  color: var(--color-text);
  font-size: 1.03rem;
  font-weight: 800;
}

.empty-state__message,
.empty-state__action {
  max-width: 42rem;
  margin: 0;
}

.empty-state__action {
  margin-block-start: var(--space-3);
}

.disclosure {
  min-width: 0;
  border-block-start: 1px solid var(--color-border);
}

.disclosure summary {
  display: flex;
  min-height: var(--touch-target);
  align-items: center;
  padding-block: var(--space-3);
  cursor: pointer;
  color: var(--color-text);
  font-weight: 760;
}

.disclosure__body {
  min-width: 0;
  padding-block: 0 var(--space-4);
  overflow-wrap: anywhere;
}

code,
kbd,
samp {
  max-width: 100%;
  color: #c6edff;
  font-family: var(--font-mono);
  overflow-wrap: anywhere;
}

pre {
  max-width: 100%;
  padding: var(--space-3);
  overflow: auto;
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
}

.sparkline,
.chart {
  display: block;
  width: 100%;
  max-width: 28rem;
  height: auto;
  color: var(--color-accent);
}
""".strip()


__all__ = ("FOUNDATION_CSS",)
