from __future__ import annotations

from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from pulse import agent, db, health, simulator
from pulse.config import ANTHROPIC_API_KEY, SERVICES

STATUS_ICON = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴", "no_data": "⚪"}

st.set_page_config(page_title="Platform Pulse", page_icon="📟", layout="wide")


@st.cache_resource
def get_conn():
    return db.connect()


def reseed(conn) -> None:
    db.reset(conn)
    simulator.generate(conn)


def render_banner(items: list[dict]) -> None:
    overall = health.platform_status(items)
    message = f"{STATUS_ICON[overall]} Platform status: {overall}"
    if overall == "critical":
        st.error(message)
    elif overall == "degraded":
        st.warning(message)
    elif overall == "healthy":
        st.success(message)
    else:
        st.info(message)


def render_cards(items: list[dict]) -> None:
    columns = st.columns(len(items))
    for column, item in zip(columns, items):
        icon = STATUS_ICON.get(item["status"], STATUS_ICON["no_data"])
        value = "n/a" if item["score"] is None else f"{item['score']:.1f}"
        column.metric(item["service"].upper(), value)
        if item["score"] is None:
            column.caption(f"{icon} no data")
            continue
        column.caption(
            f"{icon} {item['status']} · success {item['success_rate'] * 100:.1f}% · "
            f"p95 {item['p95_latency_ms']:.0f} ms · queue {item['queue_depth']:.0f} · "
            f"open incidents {item['open_incidents']}"
        )


def render_trends(conn, services: list[str], hours: int) -> None:
    latest = db.latest_ts(conn)
    if latest is None:
        return
    since = db.to_ts(db.from_ts(latest) - timedelta(hours=hours))
    frame = pd.DataFrame(db.fetch_metrics(conn, since=since))
    frame = frame[frame["service"].isin(services)]
    if frame.empty:
        st.info("No metrics for the selected filters.")
        return
    frame["ts"] = pd.to_datetime(frame["ts"])
    frame["success_pct"] = frame["success_rate"] * 100

    success = px.line(frame, x="ts", y="success_pct", color="service", title="Success rate (%)")
    success.add_hline(y=health.SLO_SUCCESS_RATE * 100, line_dash="dash", annotation_text="SLO")
    latency = px.line(frame, x="ts", y="p95_latency_ms", color="service", title="p95 latency (ms)")
    queue = px.line(frame, x="ts", y="queue_depth", color="service", title="Queue depth")
    errors = px.line(frame, x="ts", y="error_count", color="service", title="Errors per interval")

    left, right = st.columns(2)
    left.plotly_chart(success, use_container_width=True)
    right.plotly_chart(latency, use_container_width=True)
    left.plotly_chart(queue, use_container_width=True)
    right.plotly_chart(errors, use_container_width=True)


def render_incidents(conn, services: list[str]) -> None:
    show_resolved = st.checkbox("Include resolved", value=True)
    rows = [
        r
        for r in db.fetch_incidents(conn, active_only=not show_resolved)
        if r["service"] in services
    ]
    if not rows:
        st.info("No incidents for the selected filters.")
        return
    frame = pd.DataFrame(rows)[
        ["id", "severity", "service", "status", "title", "opened_at", "resolved_at"]
    ]
    st.dataframe(frame, use_container_width=True, hide_index=True)

    selected = st.selectbox("Incident", [r["id"] for r in rows])
    incident = db.get_incident(conn, int(selected))
    if incident is None:
        return
    st.markdown(f"**{incident['severity']} · {incident['service']} · {incident['title']}**")
    st.write(incident["summary"])
    if st.button("Triage with agent"):
        with st.spinner("Triaging..."):
            result = agent.triage_incident(int(selected))
        st.markdown(result.answer)
        st.caption(f"via {result.mode} agent · tools: {', '.join(result.tools_used) or 'none'}")


def render_logs(conn, services: list[str]) -> None:
    left, right = st.columns(2)
    service = left.selectbox("Service", services)
    level = right.selectbox("Level", ["All", "ERROR", "WARN", "INFO"])
    rows = db.fetch_logs(
        conn, service=service, level=None if level == "All" else level, limit=100
    )
    if not rows:
        st.info("No log lines.")
        return
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_ask() -> None:
    if not ANTHROPIC_API_KEY:
        st.caption("ANTHROPIC_API_KEY not set: the agent runs in offline summary mode.")
    question = st.text_input("Ask about platform health, incidents, or runbooks")
    if st.button("Ask") and question.strip():
        with st.spinner("Thinking..."):
            result = agent.ask(question.strip())
        st.markdown(result.answer)
        st.caption(f"via {result.mode} agent · tools: {', '.join(result.tools_used) or 'none'}")


def main() -> None:
    conn = get_conn()
    st.title("Platform Pulse")
    st.caption("Customer-experience view of platform health. Telemetry is simulated.")

    with st.sidebar:
        st.header("Filters")
        window = st.select_slider("Health window (minutes)", options=[15, 30, 60, 120], value=30)
        hours = st.slider("Trend range (hours)", min_value=1, max_value=24, value=6)
        services = st.multiselect("Services", list(SERVICES), default=list(SERVICES))
        if st.button("Reseed simulated data"):
            reseed(conn)
            st.rerun()

    if db.latest_ts(conn) is None:
        st.info("No telemetry yet.")
        if st.button("Seed simulated data"):
            reseed(conn)
            st.rerun()
        return

    if not services:
        st.warning("Select at least one service.")
        return

    items = [health.service_health(conn, s, window) for s in services]
    render_banner(items)
    render_cards(items)
    st.caption(f"Data as of {items[0]['as_of']} UTC")

    trends, incidents, logs, ask = st.tabs(["Trends", "Incidents", "Logs", "Ask the agent"])
    with trends:
        render_trends(conn, services, hours)
    with incidents:
        render_incidents(conn, services)
    with logs:
        render_logs(conn, services)
    with ask:
        render_ask()


main()
