"""Streamlit dashboard for the Composite Macro Fragility Index."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.index_calculator import PILLAR_METRICS, calculate_index
from main import cache_for, load_config, refresh_all

ZONE_COLORS = {"Green": "#38b26d", "Yellow": "#eab308", "Orange": "#f97316", "Red": "#ef4444", "Unavailable": "#64748b"}
DISPLAY_INTERVALS = {"15 minutes": 15 * 60, "1 hour": 60 * 60, "6 hours": 6 * 60 * 60, "12 hours": 12 * 60 * 60, "1 day": 24 * 60 * 60}


@st.cache_resource
def services():
    config = load_config()
    return config, cache_for(config)


def load_series(cache) -> dict[str, pd.Series]:
    names = {metric for metrics in PILLAR_METRICS.values() for metric in metrics}
    return {name: cache.series(name, 430) for name in names}


def index_snapshot(cache, config):
    series = load_series(cache)
    geo = cache.geo_history(1)
    geo_score = None if geo.empty else float(geo.iloc[0].score)
    return calculate_index(series, geo_score, config["weights"]), series, geo


def prior_score(series: dict[str, pd.Series], geo_score: float | None, config: dict) -> float | None:
    earlier = {name: values.iloc[:-5] for name, values in series.items() if len(values) > 5}
    return calculate_index(earlier, geo_score, config["weights"]).score


def line_chart(title: str, explanation: str, series: list[tuple[str, pd.Series]], threshold: float | None = None):
    """Render a chart followed by a plain-language guide to its signal."""
    st.caption(explanation)
    chart = go.Figure()
    for name, values in series:
        if not values.empty:
            chart.add_trace(go.Scatter(x=values.index, y=values.values, name=name, mode="lines"))
    if threshold is not None:
        chart.add_hline(y=threshold, line_dash="dash", line_color="#f97316", annotation_text=f"Watch: {threshold:g}")
    chart.update_layout(title=title, height=330, margin=dict(l=10, r=10, t=45, b=10), legend=dict(orientation="h"), template="plotly_white")
    st.plotly_chart(chart, width="stretch")


def fragility_history_chart(history: pd.DataFrame) -> None:
    st.subheader("Macro Fragility Trend")
    st.caption("One snapshot is stored after every data refresh. Higher values mean greater systemic fragility; multiple refreshes on the same day update that day’s point.")
    if history.empty:
        st.info("The trend begins after the first data refresh. Run a scheduled refresh daily to build a long-term history.")
        return
    if len(history) == 1:
        st.info("Today's snapshot is saved. The line chart will appear after the next daily refresh adds a second point.")
        return
    chart = go.Figure(go.Scatter(x=history.observed_at, y=history.score, mode="lines+markers", name="Composite score", line={"color": "#334155", "width": 3}))
    for lower, upper, color, label in [(0, 35, "#dcfce7", "Green"), (35, 60, "#fef9c3", "Yellow"), (60, 80, "#ffedd5", "Orange"), (80, 100, "#fee2e2", "Red")]:
        chart.add_hrect(y0=lower, y1=upper, fillcolor=color, opacity=.45, line_width=0, annotation_text=label, annotation_position="right")
    chart.update_yaxes(range=[0, 100], title="Fragility score")
    chart.update_layout(height=310, margin=dict(l=10, r=10, t=25, b=10), template="plotly_white", showlegend=False)
    st.plotly_chart(chart, width="stretch")


def render_geo_table(geo_log: pd.DataFrame) -> None:
    st.caption("Ratings are local-model heuristics based on RSS headline batches—not verified intelligence. Scores of 1 are low and 5 are high.")
    if geo_log.empty:
        st.info("No local geopolitical assessment has been stored yet.")
        return
    visible = geo_log.rename(columns={"assessed_at": "Assessed", "hormuz_shipping_threat": "Hormuz", "refinery_strike_damage": "Refinery damage", "peace_deescalation_signals": "De-escalation", "summary": "Summary", "score": "Score", "status": "Status"})
    # DataFrame cells do not reliably wrap long text; escaped HTML gives the narrative its own wrapping column.
    st.markdown(visible.to_html(index=False, escape=True, classes="geo-table"), unsafe_allow_html=True)


def render_dashboard(config: dict, cache) -> None:
    result, series, geo = index_snapshot(cache, config)
    if result.score is None:
        st.info("No usable observations yet. Use **Refresh Data Now** or run `python main.py --seed-demo` to explore the dashboard offline.")
        return
    prior = prior_score(series, None if geo.empty else float(geo.iloc[0].score), config)
    delta = None if prior is None else result.score - prior
    color = ZONE_COLORS[result.zone]
    gauge, headline = st.columns([1, 2])
    with gauge:
        figure = go.Figure(go.Indicator(mode="gauge+number", value=result.score, number={"suffix": " / 100", "font": {"size": 42}}, gauge={"axis": {"range": [0, 100]}, "bar": {"color": color}, "steps": [{"range": [0, 35], "color": "#dcfce7"}, {"range": [35, 60], "color": "#fef9c3"}, {"range": [60, 80], "color": "#ffedd5"}, {"range": [80, 100], "color": "#fee2e2"}]}))
        figure.update_layout(height=250, margin=dict(l=10, r=10, t=20, b=0))
        st.plotly_chart(figure, width="stretch")
    with headline:
        st.subheader(f"{result.zone} regime", divider="red" if result.zone == "Red" else None)
        st.markdown(f"<span style='font-size:2.2rem;color:{color};font-weight:700'>{result.score:.1f}</span> composite fragility", unsafe_allow_html=True)
        st.metric("5-trading-day change", "—" if delta is None else f"{delta:+.1f} points")
        st.caption(f"Data coverage: {result.data_quality}% of pillars. Missing pillars are excluded and remaining weights are rebalanced. Higher values always mean more stress.")
    cols = st.columns(4)
    for column, (pillar, value) in zip(cols, result.pillars.items()):
        column.metric(pillar.replace("_", " ").title(), "Unavailable" if value is None else f"{value:.1f}")

    fragility_history_chart(cache.fragility_history())
    energy, credit, market, geo_tab = st.tabs(["Energy & Physical Flow", "Credit & Bonds", "AI & Equity Breadth", "Geopolitical Intelligence"])
    with energy:
        line_chart("Energy prices", "Rising crude can increase inflation and supply-chain pressure. Compare the direction and pace of Brent and WTI, not a single price level.", [("Brent", series["brent"]), ("WTI", series["wti"])])
        line_chart("Refinery margin proxy: heating-oil crack spread", "A rising crack spread means refined fuels are becoming expensive relative to crude, which can signal refinery or downstream bottlenecks.", [("Crack spread ($/bbl)", series["crack_spread"])])
        line_chart("SPR inventory trajectory", "Falling Strategic Petroleum Reserve inventory means a smaller emergency buffer. This metric is scored inversely: lower stocks raise fragility.", [("SPR (million barrels)", series["spr_inventory"])])
    with credit:
        line_chart("High-yield option-adjusted spread", "This is the extra yield investors demand to own riskier corporate debt. A widening spread indicates tightening credit conditions; the dashed 450 bps line is a watch level.", [("HY spread (bps)", series["high_yield_spread"])], 450)
        line_chart("Rates and curve", "Higher 10-year yields increase financing costs. A low or negative 10Y–2Y slope can reflect growth stress; inspect each line’s direction rather than their relative height.", [("10Y Treasury (%)", series["treasury_10y"]), ("10Y–2Y spread (%)", series["yield_curve"])])
        line_chart("Financial conditions", "High real yields pressure valuations and borrowing. A rising Financial Stress Index indicates a broader deterioration in financial-market conditions.", [("10Y TIPS real yield (%)", series["real_yield_10y"]), ("STL Financial Stress Index", series["financial_stress"])])
    with market:
        line_chart("Market concentration: SPY / RSP", "When this ratio rises, large-cap stocks are outperforming the equal-weight market—evidence that a rally may depend on fewer companies.", [("SPY / RSP", series["concentration_ratio"])])
        line_chart("Technology and liquidity", "Rising SOXX/XLP can show tech leadership; a rising VIX signals anxiety; a stronger dollar can tighten global liquidity. These have different units, so compare their direction, not their height.", [("SOXX / XLP", series["semi_staples_ratio"]), ("VIX", series["vix"]), ("Dollar index", series["dollar"])])
        line_chart("Private-credit proxy: BIZD / SPY", "A falling BIZD/SPY ratio suggests business-development companies are lagging broad equities, a potential warning for private-credit conditions.", [("BIZD / SPY", series["bdc_relative"])])
    with geo_tab:
        render_geo_table(cache.geo_history(30))


def app() -> None:
    st.set_page_config(page_title="Macroeconomic Fragility Barometer", page_icon="◉", layout="wide")
    st.markdown("""<style>
        .block-container {max-width: 1400px; padding-top: 2rem;}
        [data-testid='stMetricValue'] {font-size: 2rem;}
        .geo-table {width: 100%; table-layout: fixed; border-collapse: collapse; font-size: .9rem;}
        .geo-table th, .geo-table td {padding: .55rem; border: 1px solid #d7dce5; vertical-align: top; text-align: left; white-space: normal; overflow-wrap: anywhere;}
        .geo-table th:nth-child(6), .geo-table td:nth-child(6) {width: 38%; min-width: 18rem;}
    </style>""", unsafe_allow_html=True)
    config, cache = services()
    st.title("Macroeconomic Fragility Barometer")
    st.caption("Macro fragility early-warning dashboard · Local cache · Data is informational, not investment advice.")
    controls, interval_control, auto_control = st.columns([1, 1, 1])
    with controls:
        manual_refresh = st.button("Refresh Data Now", type="primary", width="content")
    with interval_control:
        interval_label = st.selectbox("Dashboard refresh interval", list(DISPLAY_INTERVALS), index=4, help="How often this open browser dashboard rereads the local cache.")
    with auto_control:
        auto_collect = st.toggle("Also refresh live sources", value=False, help="Off by default so simply viewing the dashboard never starts a slow Ollama run. Use Task Scheduler for unattended daily collection, or turn this on while the app stays open.")
    if manual_refresh:
        with st.spinner("Updating sources and local cache. The local Ollama analysis may take several minutes…"):
            reports = refresh_all(config)
        warnings = [warning for report in reports for warning in getattr(report, "warnings", [])]
        if warnings:
            st.warning("Refresh completed with fallbacks: " + " | ".join(warnings))
        else:
            st.success("Refresh completed.")
        st.rerun()

    @st.fragment(run_every=timedelta(seconds=DISPLAY_INTERVALS[interval_label]))
    def live_dashboard() -> None:
        if auto_collect:
            with st.spinner("Scheduled source refresh in progress; Ollama can take several minutes…"):
                refresh_all(config)
        render_dashboard(config, cache)

    live_dashboard()


if __name__ == "__main__":
    app()
