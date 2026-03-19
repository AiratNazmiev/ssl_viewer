from __future__ import annotations

import math

from .constants import EARTH_METERS_PER_DEG_LAT, EPS


def wrap_360(x: float) -> float:
    return x % 360.0


def bearing_deg_from_en(east_m: float, north_m: float) -> float | None:
    if abs(east_m) < EPS and abs(north_m) < EPS:
        return None
    return wrap_360(math.degrees(math.atan2(east_m, north_m)))


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
    a = math.radians(wrap_360(heading_deg))
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
    re, rn = heading_unit(heading_deg + 90.0)

    east_m = forward_m * fe + right_m * re
    north_m = forward_m * fn + right_m * rn
    return pos_from_local_en(lon0, lat0, east_m, north_m, z_m)


def endpoint_from_array_az_el(
    lon0: float,
    lat0: float,
    array_x_heading_deg: float,
    array_azimuth_deg: float,
    array_elevation_deg: float,
    ray_length_m: float,
    source_z_m: float,
) -> tuple[list[float], float | None]:
    """
    Convert planar-array az/el to a world-space ray endpoint.

    Assumptions:
      - local +x lies in the ground plane and has heading array_x_heading_deg
      - local +y lies in the ground plane and is 90 deg CCW from +x
      - local +z is world up

    Array azimuth/elevation convention:
      - azimuth is CCW from local +x in the local x-y plane
      - elevation is above the local x-y plane toward +z

    Local ray:
      x = cos(el) * cos(az)
      y = cos(el) * sin(az)
      z = sin(el)
    """
    az = math.radians(array_azimuth_deg)
    el = math.radians(array_elevation_deg)

    x_m = ray_length_m * math.cos(el) * math.cos(az)
    y_m = ray_length_m * math.cos(el) * math.sin(az)
    z_m = ray_length_m * math.sin(el)

    xe, xn = heading_unit(array_x_heading_deg)
    ye, yn = heading_unit(array_x_heading_deg - 90.0)

    east_m = x_m * xe + y_m * ye
    north_m = x_m * xn + y_m * yn
    world_z_m = source_z_m + z_m

    end_pos = pos_from_local_en(lon0, lat0, east_m, north_m, world_z_m)
    horizontal_bearing_deg = bearing_deg_from_en(east_m, north_m)
    return end_pos, horizontal_bearing_deg


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
