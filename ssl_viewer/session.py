from __future__ import annotations

from typing import Optional

import streamlit as st

from .constants import DEFAULT_ENDPOINT
from .receiver import Receiver


def stop_receiver() -> None:
    old_rx = st.session_state.get("rx")
    if old_rx is not None:
        old_rx.close()
    st.session_state["rx"] = None
    st.session_state["rx_key"] = None
    st.session_state["latest_msg"] = None


def ensure_receiver(
    enabled: bool,
    endpoint: str,
    hwm: int,
    topic: str,
    username: Optional[str],
    password: Optional[str],
) -> Receiver | None:
    key = (enabled, endpoint, int(hwm), topic, username, password)
    old_key = st.session_state.get("rx_key")
    old_rx = st.session_state.get("rx")

    if not enabled:
        stop_receiver()
        st.session_state["rx_error"] = None
        return None

    if old_rx is not None and old_key == key:
        return old_rx

    try:
        new_rx = Receiver(
            endpoint,
            hwm=int(hwm),
            topic=topic,
            username=username,
            password=password,
        )
    except Exception as e:
        st.session_state["rx_error"] = str(e)
        return old_rx

    if old_rx is not None:
        old_rx.close()

    st.session_state["rx"] = new_rx
    st.session_state["rx_key"] = key
    st.session_state["rx_error"] = None
    st.session_state["latest_msg"] = None
    return new_rx


def init_session_state() -> None:
    defaults = {
        "latest_msg": None,
        "rx": None,
        "rx_key": None,
        "rx_error": None,
        "conn_enabled": True,
        "conn_endpoint": DEFAULT_ENDPOINT,
        "conn_hwm": 2,
        "conn_topic": "",
        "conn_username": "",
        "conn_password": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
