from __future__ import annotations

import streamlit as st

from .layers import build_dynamic_layers, build_static_layers, make_deck
from .receiver import Receiver
from .session import ensure_receiver, init_session_state
from .telemetry import TargetTelemetry


def render_sidebar() -> dict[str, object]:
    with st.sidebar:
        anchor_lat = st.number_input("Anchor latitude", value=55.790450, format="%.6f")
        anchor_lon = st.number_input("Anchor longitude", value=49.124100, format="%.6f")

        array_x_heading_deg = st.slider(
            "Array +x heading (clockwise from north)",
            min_value=0.0,
            max_value=359.0,
            value=120.0,
            step=1.0,
        )

        refresh_ms = st.slider("Refresh interval (ms)", 50, 1000, 100, 50)

        mic_radius_m = st.slider("Mic body radius (m)", 0.1, 3.0, 1.0, 0.1)
        mic_height_m = st.slider("Mic body height (m)", 0.1, 3.0, 1.0, 0.1)
        ray_length_m = st.slider("Ray length (m)", 2.0, 60.0, 16.0, 0.5)

        show_basemap = st.checkbox("Show basemap", value=True)

        st.divider()

        with st.form("connection_form", clear_on_submit=False):
            form_enabled = st.checkbox(
                "Enable live telemetry",
                value=bool(st.session_state["conn_enabled"]),
            )
            form_endpoint = st.text_input(
                "Connect endpoint",
                value=str(st.session_state["conn_endpoint"]),
            )
            form_hwm = st.number_input(
                "Receiver HWM",
                min_value=1,
                max_value=1000,
                value=int(st.session_state["conn_hwm"]),
                step=1,
            )
            form_topic = st.text_input(
                "Topic filter",
                value=str(st.session_state["conn_topic"]),
            )
            form_username = st.text_input(
                "Username",
                value=str(st.session_state["conn_username"]),
            )
            form_password = st.text_input(
                "Password",
                value=str(st.session_state["conn_password"]),
                type="password",
            )
            apply_conn = st.form_submit_button("Apply connection settings")

        if apply_conn:
            st.session_state["conn_enabled"] = bool(form_enabled)
            st.session_state["conn_endpoint"] = str(form_endpoint).strip()
            st.session_state["conn_hwm"] = int(form_hwm)
            st.session_state["conn_topic"] = str(form_topic)
            st.session_state["conn_username"] = str(form_username)
            st.session_state["conn_password"] = str(form_password)

    return {
        "anchor_lat": anchor_lat,
        "anchor_lon": anchor_lon,
        "array_x_heading_deg": array_x_heading_deg,
        "refresh_ms": refresh_ms,
        "mic_radius_m": mic_radius_m,
        "mic_height_m": mic_height_m,
        "ray_length_m": ray_length_m,
        "show_basemap": show_basemap,
    }


def render_metrics(msg: TargetTelemetry | None, horizontal_bearing_deg: float | None) -> None:
    top1, top2, top3, top4, top5, top6 = st.columns(6)

    if msg is not None:
        top1.metric("Array azimuth", f"{msg.az_deg:.1f}°")
        top2.metric("Array elevation", f"{msg.el_deg:.1f}°")
        top3.metric(
            "Horizontal bearing",
            "vertical" if horizontal_bearing_deg is None else f"{horizontal_bearing_deg:.1f}°",
        )
        top4.metric("Confidence", f"{msg.confidence:.2f}")
        top5.metric("Target ID", str(msg.target_id))
        top6.metric("Latency", f"{msg.latency_ms:.1f} ms")
    else:
        top1.metric("Array azimuth", "-")
        top2.metric("Array elevation", "-")
        top3.metric("Horizontal bearing", "-")
        top4.metric("Confidence", "-")
        top5.metric("Target ID", "-")
        top6.metric("Latency", "-")


def render_status(rx: Receiver | None) -> None:
    status1, status2, status3 = st.columns(3)
    status1.metric("Subscriber", "running" if rx is not None else "disabled")
    status2.metric("Superseded", str(rx.superseded if rx is not None else 0))
    status3.metric("Recv errors", str(rx.recv_errors if rx is not None else 0))


def main() -> None:
    st.set_page_config(layout="wide")
    st.title("SSL viewer")

    init_session_state()
    settings = render_sidebar()

    rx_username = st.session_state["conn_username"] or None
    rx_password = st.session_state["conn_password"] or None

    ensure_receiver(
        enabled=bool(st.session_state["conn_enabled"]),
        endpoint=str(st.session_state["conn_endpoint"]),
        hwm=int(st.session_state["conn_hwm"]),
        topic=str(st.session_state["conn_topic"]),
        username=rx_username,
        password=rx_password,
    )

    if st.session_state["rx_error"]:
        st.error(f"Receiver startup failed: {st.session_state['rx_error']}")

    refresh_s = float(settings["refresh_ms"]) / 1000.0

    @st.fragment(run_every=refresh_s)
    def live_view() -> None:
        rx: Receiver | None = st.session_state.get("rx")

        if rx is not None:
            latest = rx.poll_latest()
            if latest is not None:
                st.session_state["latest_msg"] = latest

        msg: TargetTelemetry | None = st.session_state.get("latest_msg")

        static_layers = build_static_layers(
            anchor_lon=float(settings["anchor_lon"]),
            anchor_lat=float(settings["anchor_lat"]),
            array_x_heading_deg=float(settings["array_x_heading_deg"]),
            mic_radius_m=float(settings["mic_radius_m"]),
            mic_height_m=float(settings["mic_height_m"]),
        )

        if msg is not None:
            dynamic_layers, horizontal_bearing_deg = build_dynamic_layers(
                anchor_lon=float(settings["anchor_lon"]),
                anchor_lat=float(settings["anchor_lat"]),
                array_x_heading_deg=float(settings["array_x_heading_deg"]),
                mic_height_m=float(settings["mic_height_m"]),
                ray_length_m=float(settings["ray_length_m"]),
                array_azimuth_deg=msg.az_deg,
                array_elevation_deg=msg.el_deg,
            )
            layers = static_layers + dynamic_layers
        else:
            horizontal_bearing_deg = None
            layers = static_layers

        render_metrics(msg, horizontal_bearing_deg)
        render_status(rx)

        deck = make_deck(
            anchor_lon=float(settings["anchor_lon"]),
            anchor_lat=float(settings["anchor_lat"]),
            layers=layers,
            show_basemap=bool(settings["show_basemap"]),
        )
        st.pydeck_chart(deck, height=700, width="stretch")

    live_view()
