from __future__ import annotations

import math

from crypto_rsi_scanner.event_alpha.dashboard.charts import (
    ChartPoint,
    render_activity_chart,
    render_history_chart,
    render_price_chart,
    render_progress_chart,
    render_relative_chart,
)


def test_history_chart_is_responsive_accessible_and_escapes_all_supplied_text():
    svg = render_history_chart(
        [
            {"when": '<start & "open">', "metric": 10},
            {"when": "latest</text><script>alert(1)</script>", "metric": 12},
        ],
        title='Price <img src=x onerror="alert(1)">',
        summary="Measured & reviewed </desc><script>bad()</script>",
        state_detail='Trusted "history" <unsafe>',
        value_key="metric",
        label_key="when",
    )

    assert '<svg class="radar-inline-chart" viewBox="0 0 640 180"' in svg
    assert 'width="100%"' in svg
    assert 'preserveAspectRatio="xMidYMid meet"' in svg
    assert 'style="display:block;width:100%;height:auto"' in svg
    assert 'role="img"' in svg
    assert 'aria-label="Price &lt;img src=x onerror=&quot;alert(1)&quot;&gt;"' in svg
    assert "<title>Price &lt;img src=x onerror=\"alert(1)\"&gt;</title>" in svg
    assert "<desc>" in svg and "Evidence state: current history." in svg
    assert "&lt;script&gt;" in svg
    assert "<script>" not in svg
    assert "<img" not in svg
    assert "&lt;start &amp;" in svg
    assert "latest&lt;/text&gt;…" in svg


def test_missing_cold_warming_and_proxy_states_are_visible_and_honest():
    missing = render_history_chart([], title="No price", state="ready")
    assert "History unavailable" in missing
    assert "Start · unavailable" in missing
    assert "Latest · unavailable" in missing
    assert "0 usable observations" in missing
    assert "<polyline" not in missing

    cold = render_history_chart(
        [ChartPoint("14 Jul 12:00", 100.0)],
        title="Cold price",
        state="ready",
    )
    assert "Cold baseline" in cold
    assert "Only observation" not in cold
    assert "14 Jul 12:00 · 100" in cold
    assert '<circle class="chart-point"' in cold
    assert "<polyline" not in cold

    warming = render_history_chart(
        [("12:00", 1), ("13:00", 2), ("14:00", 3)],
        title="Warming score",
        state="warming",
        state_detail="Three of eight required samples",
        proxy=True,
    )
    assert "Warming baseline · Proxy evidence" in warming
    assert "Three of eight required samples." in warming
    assert "explicitly proxy-derived evidence" in warming
    assert '<polyline class="chart-line"' in warming


def test_timestamp_axis_labels_are_compact_enough_for_phone_charts() -> None:
    svg = render_history_chart(
        [
            ("2026-07-13T15:17:06.228233+00:00", 41.23),
            ("2026-07-14T00:29:40.814498+00:00", 41.86),
        ],
        title="Compact phone axis",
        value_format="price",
    )

    assert "Jul 13 15:17Z · $41.23" in svg
    assert "Jul 14 00:29Z · $41.86" in svg
    assert "2026-07-13T15:17" not in svg


def test_nonfinite_observations_are_explicit_gaps_and_never_svg_coordinates():
    svg = render_history_chart(
        [
            ("a", 1.0),
            ("missing", None),
            ("nan", math.nan),
            ("infinite", math.inf),
            ("b", 2.0),
            ("c", 3.0),
        ],
        title="Gapped history",
    )

    assert svg.count('<polyline class="chart-line"') == 1
    assert svg.count('<circle class="chart-point"') == 1
    assert 'points="' in svg
    assert "nan" not in svg.lower()
    assert "inf" not in svg.lower()


def test_large_sequence_is_evenly_bounded_and_preserves_start_and_end():
    history = [(f"t{index}", index) for index in range(1_000)]
    svg = render_history_chart(
        history,
        title="Bounded history",
        max_points=10,
    )

    assert "10 plotted from 1000 supplied" in svg
    assert "evenly downsampled bounded view" in svg
    assert "t0" in svg
    assert "t999" in svg
    points = svg.split('points="', 1)[1].split('"', 1)[0].split()
    assert len(points) == 10


def test_generic_iterable_is_hard_capped_without_being_presented_as_complete():
    svg = render_history_chart(
        ((f"row-{index}", index) for index in range(700)),
        title="Generator history",
        max_points=12,
    )

    assert "Bounded view" in svg
    assert "generic iterable input was capped" in svg
    assert "12 plotted after inspecting at least 513 supplied" in svg


def test_metric_wrappers_cover_price_activity_relative_and_progression():
    history = [
        {
            "observed_at": "14 Jul 12:00",
            "price": 100.0,
            "volume_24h_usd": 1_200_000,
            "turnover_24h_usd": 800_000,
            "relative_return_vs_btc_4h": -2.0,
            "relative_return_vs_eth_4h": -1.0,
            "actionability_score": 55,
            "baseline_samples": 2,
        },
        {
            "observed_at": "14 Jul 13:00",
            "price": 105.0,
            "volume_24h_usd": 1_600_000,
            "turnover_24h_usd": 900_000,
            "relative_return_vs_btc_4h": 3.0,
            "relative_return_vs_eth_4h": 1.5,
            "actionability_score": 72,
            "baseline_samples": 3,
        },
    ]

    price = render_price_chart(history)
    volume = render_activity_chart(history, activity="volume")
    turnover = render_activity_chart(history, activity="turnover")
    btc = render_relative_chart(history, benchmark="BTC")
    eth = render_relative_chart(history, benchmark="ETH", proxy=True)
    score = render_progress_chart(history, progress="score")
    baseline = render_progress_chart(history, progress="baseline")

    assert "Price history" in price and "$105.00" in price
    assert "Volume history" in volume and "1.6M" in volume
    assert "Turnover history" in turnover and "900.0K" in turnover
    assert ">-0" not in volume
    assert ">-0" not in turnover
    assert volume.count('<rect class="chart-bar"') == 2
    assert "Relative performance vs BTC" in btc and "+3.0%" in btc
    assert '<line class="chart-zero"' in btc
    assert "Relative performance vs ETH" in eth and "Proxy evidence" in eth
    assert "Score progression" in score and "100/100" in score
    assert "Baseline progression" in baseline and "3" in baseline


def test_unknown_state_fails_closed_to_missing_instead_of_claiming_current_history():
    svg = render_history_chart(
        [("start", 1), ("end", 2)],
        title="Unknown state",
        state="mystery",
    )

    assert "History unavailable" in svg
    assert "Current history" not in svg
    assert "<polyline" not in svg
