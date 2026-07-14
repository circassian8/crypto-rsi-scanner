# crypto-rsi-scanner

Research-oriented crypto RSI scanner and human-decided Event Alpha Crypto Radar.

## Local Crypto Radar dashboard

`make radar-dashboard` serves the current Crypto Decision Radar operator
generation at `http://127.0.0.1:8765/`. The seven-page terminal covers Today,
Market Radar, Ideas, Calendar, System Health, Outcomes & Learning, and Campaign
History; see the [operator guide](research/CRYPTO_DECISION_RADAR_OPERATOR_GUIDE.md).
It reads the exact run/revision manifest and local
artifacts only. Current research appears only when exact file/tree/run-row
fingerprints, the immutable run age, and a fresh strict doctor for the same
revision all agree; otherwise current pages are suppressed while Health and
clearly labeled cumulative history remain available. It does not call
providers, send notifications, trade, paper
trade, write normal RSI rows, or create `TRIGGERED_FADE`. Run
`make radar-dashboard-smoke` for the deterministic fixture/no-write render gate
and `make radar-dashboard-ux-smoke` for primary-page semantic and responsive
contracts.
`make radar-calendar-preview` prints the unified macro/crypto calendar fixture
without provider calls, artifact writes, or sends.
Integrated runs normalize scheduled and fixture rows once and persist only
payload-free accepted/rejected/deduplicated counters in the exact canonical run
row; `main.py --event-alpha-runs` shows that accounting without retaining
rejected titles, URLs, sources, or exception text.

Crypto Radar Decision Model v2 may surface transparent market-led research
ideas without a known catalyst when freshness, identity, liquidity, spread,
turnover, volume, dedupe, and safety gates pass. These are research ideas, not
trade instructions. Legacy Event Alpha routes remain separate.
Each v2 route has its own `RSI_EVENT_ALPHA_DECISION_MODEL_V2_ROUTE_*_ENABLED`
switch; these switches never authorize legacy routing or delivery.

## CI safety

GitHub Actions is configured for safe verification only. Push and pull-request
CI first checks the universal hash-pinned dependency lock and audits it for
known vulnerabilities, then runs the canonical `make verify` on Python 3.11 and
3.13 (standalone compatibility, pytest, alert render, fixture backtest, and
paper scoreboard) with `RSI_EVENT_ALERTS_ENABLED=0`. Static architecture reports
run once on 3.13. The manual Event Alpha smoke workflow runs the fixture/no-call
targets on both supported Python versions. CI does not load `.env`, provider API
keys, Telegram tokens, live-provider allow flags, live-send targets, trading,
paper trading, execution, normal RSI signal writes, or Event Alpha
`TRIGGERED_FADE` creation.

All third-party workflow actions are pinned to immutable full release commit
SHAs with readable version comments. The current checkout/setup actions use
their supported Node 24 releases; weekly Dependabot proposes reviewed SHA
updates instead of silently following mutable major tags.

`requirements.in` records direct dependency intent; `requirements.txt` is the
cross-platform, Python 3.11+-compatible hash-pinned environment used by
bootstrap and CI. Install the pinned dependency tools with
`make dependency-tools`, update the lock with
`make lock-dependencies UPGRADE=1`, and run
`make dependency-verify` before accepting dependency changes.
