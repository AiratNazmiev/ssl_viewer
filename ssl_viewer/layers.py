from __future__ import annotations

import pydeck as pdk

from .geometry import endpoint_from_array_az_el, make_arrow_polygon


def build_static_layers(
    anchor_lon: float,
    anchor_lat: float,
    array_x_heading_deg: float,
    mic_radius_m: float,
    mic_height_m: float,
) -> list[pdk.Layer]:
    source_z_m = mic_height_m * 0.82
    arrow_z_m = mic_height_m + 0.08

    az0_arrow_poly = make_arrow_polygon(
        lon0=anchor_lon,
        lat0=anchor_lat,
        heading_deg=array_x_heading_deg,
        z_m=arrow_z_m,
        tail_offset_m=max(0.45, mic_radius_m * 0.85),
        shaft_len_m=max(1.4, mic_radius_m * 1.4),
        shaft_half_w_m=max(0.18, mic_radius_m * 0.18),
        head_len_m=max(0.9, mic_radius_m * 0.8),
        head_half_w_m=max(0.42, mic_radius_m * 0.42),
    )
    az0_arrow_outline = az0_arrow_poly + [az0_arrow_poly[0]]

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
        data=[{"polygon": az0_arrow_poly}],
        id="orientation-fill",
        get_polygon="polygon",
        filled=True,
        stroked=False,
        extruded=False,
        get_fill_color=[80, 160, 255, 220],
        pickable=False,
    )

    orientation_outline = pdk.Layer(
        "PathLayer",
        data=[{"path": az0_arrow_outline}],
        id="orientation-outline",
        get_path="path",
        get_color=[235, 245, 255, 255],
        get_width=2,
        width_units="pixels",
        width_min_pixels=1,
        cap_rounded=True,
        joint_rounded=True,
        pickable=False,
    )

    return [
        mic_body,
        mic_top,
        orientation_fill,
        orientation_outline,
    ]


def build_dynamic_layers(
    anchor_lon: float,
    anchor_lat: float,
    array_x_heading_deg: float,
    mic_height_m: float,
    ray_length_m: float,
    array_azimuth_deg: float,
    array_elevation_deg: float,
) -> tuple[list[pdk.Layer], float | None]:
    source_z_m = mic_height_m * 0.82

    ray_end, horizontal_bearing_deg = endpoint_from_array_az_el(
        lon0=anchor_lon,
        lat0=anchor_lat,
        array_x_heading_deg=array_x_heading_deg,
        array_azimuth_deg=array_azimuth_deg,
        array_elevation_deg=array_elevation_deg,
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
        data=[{"path": ray_path}],
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

    return [ray_glow, ray_core, ray_tip], horizontal_bearing_deg


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
