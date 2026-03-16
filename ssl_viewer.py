from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from typing import Any

import pydeck as pdk
import streamlit as st
import zmq

st.set_page_config(layout="wide")

EARTH_METERS_PER_DEG_LAT = 111_320.0


# -----------------------------
# telemetry.py
# -----------------------------

@dataclass(slots=True)
class TargetTelemetry:
    az_deg: float
    el_deg: float
    confidence: float = 1.0
    target_id: int = 1
    ts_ns: int = 0

    def __post_init__(self) -> None:
        self.az_deg = float(self.az_deg)
        self.el_deg = float(self.el_deg)
        self.confidence = float(self.confidence)
        self.target_id = int(self.target_id)
        self.ts_ns = time.time_ns() if self.ts_ns == 0 else int(self.ts_ns)

        if not math.isfinite(self.az_deg):
            raise ValueError("az_deg must be finite")
        if not math.isfinite(self.el_deg):
            raise ValueError("el_deg must be finite")
        if not math.isfinite(self.confidence):
            raise ValueError("confidence must be finite")

        if not -180.0 <= self.az_deg <= 180.0:
            raise ValueError("az_deg out of range")
        if not -90.0 <= self.el_deg <= 90.0:
            raise ValueError("el_deg out of range")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence out of range")

    def to_dict(self) -> dict[str, Any]:
        return {
            "az_deg": self.az_deg,
            "el_deg": self.el_deg,
            "confidence": self.confidence,
            "target_id": self.target_id,
            "ts_ns": self.ts_ns,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetTelemetry":
        return cls(
            az_deg=data["az_deg"],
            el_deg=data["el_deg"],
            confidence=data.get("confidence", 1.0),
            target_id=data.get("target_id", 1),
            ts_ns=data.get("ts_ns", 0),
        )

    def to_json_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), separators=(",", ":")).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> "TargetTelemetry":
        obj = json.loads(payload.decode("utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("expected JSON object")
        return cls.from_dict(obj)

    @property
    def latency_ms(self) -> float:
        return (time.time_ns() - self.ts_ns) * 1e-6


# -----------------------------
# receiver thread
# -----------------------------

class ReceiverThread(threading.Thread):
    """
    Latest-state-wins telemetry receiver.
    """

    def __init__(self, endpoint: str, *, hwm: int = 2) -> None:
        super().__init__(name="TelemetryReceiver", daemon=True)

        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._latest: TargetTelemetry | None = None
        self._dropped_overwritten = 0
        self._recv_errors = 0

        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.PULL)
        self._sock.setsockopt(zmq.RCVHWM, int(hwm))
        self._sock.setsockopt(zmq.LINGER, 0)
        self._sock.setsockopt(zmq.RCVTIMEO, 100)
        self._sock.bind(endpoint)

    @property
    def dropped_overwritten(self) -> int:
        with self._lock:
            return self._dropped_overwritten

    @property
    def recv_errors(self) -> int:
        with self._lock:
            return self._recv_errors

    def pop_latest(self) -> TargetTelemetry | None:
        with self._lock:
            msg = self._latest
            self._latest = None
            return msg

    def _store_latest(self, msg: TargetTelemetry) -> None:
        with self._lock:
            if self._latest is not None:
                self._dropped_overwritten += 1
            self._latest = msg

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                obj = self._sock.recv_json()
                if not isinstance(obj, dict):
                    raise ValueError("expected JSON object")
                msg = TargetTelemetry.from_dict(obj)
                self._store_latest(msg)

            except zmq.Again:
                continue

            except zmq.ZMQError:
                if self._stop_event.is_set():
                    break
                with self._lock:
                    self._recv_errors += 1

            except Exception:
                with self._lock:
                    self._recv_errors += 1

    def close(self, timeout: float = 1.0) -> None:
        self._stop_event.set()
        try:
            self._sock.close()
        finally:
            if self.is_alive():
                self.join(timeout=timeout)


# -----------------------------
# geometry helpers
# -----------------------------

def wrap_deg(x: float) -> float:
    return x % 360.0


def offset_m_to_lnglat(
    lon0: float,
    lat0: float,
    east_m: float,
    north_m: float,
) -> tuple[float, float]:
    dlat = north_m / EARTH_METERS_PER_DEG_LAT
    dlon = east_m / (EARTH_METERS_PER_DEG_LAT * math.cos(math.radians(lat0)))
    return lon0 + dlon, lat0 + dlat


def heading_unit(heading_deg: float) -> tuple[float, float]:
    """
    0 deg = north, 90 deg = east, clockwise positive.
    Returns (east, north).
    """
    a = math.radians(wrap_deg(heading_deg))
    return math.sin(a), math.cos(a)


def pos_from_local_en(
    lon0: float,
    lat0: float,
    east_m: float,
    north_m: float,
    z_m: float = 0.0,
) -> list[float]:
    lon, lat = offset_m_to_lnglat(lon0, lat0, east_m, north_m)
    return [lon, lat, z_m]


def pos_from_forward_right(
    lon0: float,
    lat0: float,
    heading_deg: float,
    forward_m: float,
    right_m: float,
    z_m: float = 0.0,
) -> list[float]:
    fe, fn = heading_unit(heading_deg)

    # right-hand vector in east/north plane
    re = math.cos(math.radians(heading_deg))
    rn = -math.sin(math.radians(heading_deg))

    east_m = forward_m * fe + right_m * re
    north_m = forward_m * fn + right_m * rn
    return pos_from_local_en(lon0, lat0, east_m, north_m, z_m)


def endpoint_from_az_el(
    lon0: float,
    lat0: float,
    array_heading_deg: float,
    model_azimuth_deg: float,
    model_elevation_deg: float,
    ray_length_m: float,
    source_z_m: float,
) -> tuple[list[float], float]:
    """
    Assumptions:
    - array_heading_deg: clockwise from north
    - model_azimuth_deg: relative to array forward axis, clockwise positive
    - model_elevation_deg: positive upward
    """
    world_azimuth_deg = wrap_deg(array_heading_deg + model_azimuth_deg)

    az = math.radians(world_azimuth_deg)
    el = math.radians(model_elevation_deg)

    horizontal_m = ray_length_m * math.cos(el)
    east_m = horizontal_m * math.sin(az)
    north_m = horizontal_m * math.cos(az)
    z_m = source_z_m + ray_length_m * math.sin(el)

    end_pos = pos_from_local_en(lon0, lat0, east_m, north_m, z_m)
    return end_pos, world_azimuth_deg


def make_arrow_polygon(
    lon0: float,
    lat0: float,
    heading_deg: float,
    z_m: float,
    tail_offset_m: float,
    shaft_len_m: float,
    shaft_half_w_m: float,
    head_len_m: float,
    head_half_w_m: float,
) -> list[list[float]]:
    f0 = tail_offset_m
    f1 = tail_offset_m + shaft_len_m
    f2 = tail_offset_m + shaft_len_m + head_len_m

    local_pts = [
        (f0, -shaft_half_w_m),
        (f1, -shaft_half_w_m),
        (f1, -head_half_w_m),
        (f2, 0.0),
        (f1, head_half_w_m),
        (f1, shaft_half_w_m),
        (f0, shaft_half_w_m),
    ]

    return [
        pos_from_forward_right(lon0, lat0, heading_deg, f, r, z_m)
        for f, r in local_pts
    ]


# -----------------------------
# layer builders
# -----------------------------

def build_static_layers(
    anchor_lon: float,
    anchor_lat: float,
    array_heading_deg: float,
    mic_radius_m: float,
    mic_height_m: float,
) -> list[pdk.Layer]:
    source_z_m = mic_height_m * 0.82
    arrow_z_m = mic_height_m + 0.08

    arrow_poly = make_arrow_polygon(
        lon0=anchor_lon,
        lat0=anchor_lat,
        heading_deg=array_heading_deg,
        z_m=arrow_z_m,
        tail_offset_m=max(0.45, mic_radius_m * 0.85),
        shaft_len_m=max(1.4, mic_radius_m * 1.4),
        shaft_half_w_m=max(0.18, mic_radius_m * 0.18),
        head_len_m=max(0.9, mic_radius_m * 0.8),
        head_half_w_m=max(0.42, mic_radius_m * 0.42),
    )
    arrow_outline = arrow_poly + [arrow_poly[0]]

    mic_body = pdk.Layer(
        "ColumnLayer",
        data=[{"position": [anchor_lon, anchor_lat], "height": mic_height_m}],
        id="mic-body",
        get_position="position",
        get_elevation="height",
        elevation_scale=1,
        radius=mic_radius_m,
        disk_resolution=12,
        extruded=True,
        get_fill_color=[88, 104, 140, 235],
        pickable=False,
    )

    mic_top = pdk.Layer(
        "ScatterplotLayer",
        data=[{"position": [anchor_lon, anchor_lat, source_z_m], "radius": 0.30}],
        id="mic-top",
        get_position="position",
        get_radius="radius",
        radius_units="meters",
        radius_min_pixels=4,
        filled=True,
        stroked=True,
        get_fill_color=[235, 240, 255, 255],
        get_line_color=[40, 50, 70, 255],
        get_line_width=1,
        line_width_units="pixels",
        line_width_min_pixels=1,
        pickable=False,
    )

    orientation_fill = pdk.Layer(
        "PolygonLayer",
        data=[{"polygon": arrow_poly}],
        id="orientation-fill",
        get_polygon="polygon",
        filled=True,
        stroked=False,
        extruded=False,
        get_fill_color=[0, 220, 120, 245],
        pickable=False,
    )

    orientation_outline = pdk.Layer(
        "PathLayer",
        data=[{"path": arrow_outline}],
        id="orientation-outline",
        get_path="path",
        get_color=[245, 255, 245, 255],
        get_width=2,
        width_units="pixels",
        width_min_pixels=1,
        cap_rounded=True,
        joint_rounded=True,
        pickable=False,
    )

    return [mic_body, mic_top, orientation_fill, orientation_outline]


def build_dynamic_layers(
    anchor_lon: float,
    anchor_lat: float,
    array_heading_deg: float,
    mic_height_m: float,
    ray_length_m: float,
    model_azimuth_deg: float,
    model_elevation_deg: float,
) -> tuple[list[pdk.Layer], float]:
    source_z_m = mic_height_m * 0.82

    ray_end, world_azimuth_deg = endpoint_from_az_el(
        lon0=anchor_lon,
        lat0=anchor_lat,
        array_heading_deg=array_heading_deg,
        model_azimuth_deg=model_azimuth_deg,
        model_elevation_deg=model_elevation_deg,
        ray_length_m=ray_length_m,
        source_z_m=source_z_m,
    )

    ray_path = [
        [anchor_lon, anchor_lat, source_z_m],
        ray_end,
    ]

    ray_glow = pdk.Layer(
        "PathLayer",
        data=[{"path": ray_path}],
        id="ray-glow",
        get_path="path",
        get_color=[255, 120, 0, 80],
        get_width=14,
        width_units="pixels",
        width_min_pixels=8,
        cap_rounded=True,
        joint_rounded=True,
        billboard=True,
        pickable=False,
    )

    ray_core = pdk.Layer(
        "PathLayer",
        data=[{
            "path": ray_path,
            "name": "Target direction",
            "model_azimuth_deg": round(model_azimuth_deg, 1),
            "model_elevation_deg": round(model_elevation_deg, 1),
            "world_azimuth_deg": round(world_azimuth_deg, 1),
        }],
        id="ray-core",
        get_path="path",
        get_color=[255, 235, 170, 255],
        get_width=4,
        width_units="pixels",
        width_min_pixels=3,
        cap_rounded=True,
        joint_rounded=True,
        billboard=True,
        pickable=False,
    )

    ray_tip = pdk.Layer(
        "ScatterplotLayer",
        data=[{"position": ray_end, "radius": 0.45}],
        id="ray-tip",
        get_position="position",
        get_radius="radius",
        radius_units="meters",
        radius_min_pixels=6,
        filled=True,
        stroked=True,
        get_fill_color=[255, 235, 170, 255],
        get_line_color=[255, 140, 0, 255],
        get_line_width=2,
        line_width_units="pixels",
        line_width_min_pixels=1,
        pickable=False,
    )

    return [ray_glow, ray_core, ray_tip], world_azimuth_deg


def make_deck(
    anchor_lon: float,
    anchor_lat: float,
    layers: list[pdk.Layer],
    show_basemap: bool,
) -> pdk.Deck:
    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            longitude=anchor_lon,
            latitude=anchor_lat,
            zoom=19,
            pitch=55,
            bearing=0,
        ),
        map_provider="carto" if show_basemap else None,
        map_style="dark" if show_basemap else None,
        tooltip=None,
    )


# -----------------------------
# receiver lifecycle
# -----------------------------

def stop_receiver() -> None:
    old_rx = st.session_state.get("rx")
    if old_rx is not None:
        old_rx.close()
    st.session_state["rx"] = None


def ensure_receiver(enabled: bool, endpoint: str, hwm: int) -> ReceiverThread | None:
    key = (enabled, endpoint, int(hwm))
    old_key = st.session_state.get("rx_key")
    old_rx = st.session_state.get("rx")

    if not enabled:
        stop_receiver()
        st.session_state["rx_key"] = key
        st.session_state["rx_error"] = None
        return None

    if old_rx is not None and old_key == key:
        return old_rx

    stop_receiver()

    try:
        rx = ReceiverThread(endpoint, hwm=int(hwm))
        rx.start()
        st.session_state["rx"] = rx
        st.session_state["rx_key"] = key
        st.session_state["rx_error"] = None
        return rx
    except Exception as e:
        st.session_state["rx"] = None
        st.session_state["rx_key"] = key
        st.session_state["rx_error"] = str(e)
        return None


# -----------------------------
# UI
# -----------------------------

st.title("SSL viewer")

with st.sidebar:
    anchor_lat = st.number_input("Anchor latitude", value=55.790450, format="%.6f")
    anchor_lon = st.number_input("Anchor longitude", value=49.124100, format="%.6f")

    array_heading_deg = st.slider(
        "Array heading (clockwise from north)",
        min_value=0.0,
        max_value=359.0,
        value=30.0,
        step=1.0,
    )

    refresh_ms = st.slider("Refresh interval (ms)", 100, 1000, 400, 100)

    mic_radius_m = st.slider("Mic body radius (m)", 0.1, 3.0, 1.0, 0.1)
    mic_height_m = st.slider("Mic body height (m)", 0.1, 3.0, 1.0, 0.1)
    ray_length_m = st.slider("Ray length (m)", 2.0, 60.0, 16.0, 0.5)

    show_basemap = st.checkbox("Show basemap", value=False)

    st.divider()
    telemetry_enabled = st.checkbox("Enable live telemetry", value=True)
    telemetry_endpoint = st.text_input("Bind endpoint", value="tcp://*:5555")
    telemetry_hwm = st.number_input("Receiver HWM", min_value=1, max_value=1000, value=2, step=1)

if "latest_msg" not in st.session_state:
    st.session_state["latest_msg"] = None
if "rx" not in st.session_state:
    st.session_state["rx"] = None
if "rx_key" not in st.session_state:
    st.session_state["rx_key"] = None
if "rx_error" not in st.session_state:
    st.session_state["rx_error"] = None

ensure_receiver(
    enabled=telemetry_enabled,
    endpoint=telemetry_endpoint,
    hwm=int(telemetry_hwm),
)

if st.session_state["rx_error"]:
    st.error(f"Receiver startup failed: {st.session_state['rx_error']}")

static_layers = build_static_layers(
    anchor_lon=anchor_lon,
    anchor_lat=anchor_lat,
    array_heading_deg=array_heading_deg,
    mic_radius_m=mic_radius_m,
    mic_height_m=mic_height_m,
)

refresh_s = refresh_ms / 1000.0


@st.fragment(run_every=refresh_s)
def live_view():
    rx: ReceiverThread | None = st.session_state.get("rx")

    if rx is not None:
        latest = rx.pop_latest()
        if latest is not None:
            st.session_state["latest_msg"] = latest

    msg: TargetTelemetry | None = st.session_state.get("latest_msg")

    top1, top2, top3, top4, top5, top6 = st.columns(6)

    if msg is not None:
        dynamic_layers, world_azimuth_deg = build_dynamic_layers(
            anchor_lon=anchor_lon,
            anchor_lat=anchor_lat,
            array_heading_deg=array_heading_deg,
            mic_height_m=mic_height_m,
            ray_length_m=ray_length_m,
            model_azimuth_deg=msg.az_deg,
            model_elevation_deg=msg.el_deg,
        )

        deck = make_deck(
            anchor_lon=anchor_lon,
            anchor_lat=anchor_lat,
            layers=static_layers + dynamic_layers,
            show_basemap=show_basemap,
        )

        top1.metric("Azimuth", f"{msg.az_deg:.1f}°")
        top2.metric("Elevation", f"{msg.el_deg:.1f}°")
        top3.metric("World azimuth", f"{world_azimuth_deg:.1f}°")
        top4.metric("Confidence", f"{msg.confidence:.2f}")
        #top5.metric("Latency", f"{msg.latency_ms:.1f} ms")
        top6.metric("Target ID", str(msg.target_id))

        st.pydeck_chart(deck, height=700, width="stretch")
    else:
        top1.metric("Azimuth", "-")
        top2.metric("Elevation", "-")
        top3.metric("World azimuth", "-")
        top4.metric("Confidence", "-")
        #top5.metric("Latency", "-")
        top6.metric("Target ID", "-")

        st.info("Waiting for telemetry packets...")
        deck = make_deck(
            anchor_lon=anchor_lon,
            anchor_lat=anchor_lat,
            layers=static_layers,
            show_basemap=show_basemap,
        )
        st.pydeck_chart(deck, height=700, width="stretch")

    bottom1, bottom2, bottom3 = st.columns(3)
    bottom1.metric("Receiver", "running" if rx is not None else "disabled")
    bottom2.metric("Overwritten", str(rx.dropped_overwritten if rx is not None else 0))
    bottom3.metric("Recv errors", str(rx.recv_errors if rx is not None else 0))


live_view()