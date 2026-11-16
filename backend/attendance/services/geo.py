"""Geofence verification (framework independent).

The phone reports its position (latitude, longitude) and an accuracy radius.
The server accepts a check-in only when

1. the coordinates are valid numbers inside the legal ranges,
2. the reported accuracy is good enough (not larger than a fixed maximum), and
3. the great-circle distance to the lecture location is within the radius
   configured for the session.

The reported accuracy is *not* added to the allowed radius: an imprecise fix
must never make it easier to pass the check.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (IUGG), metres


def is_valid_coordinate(latitude: float, longitude: float) -> bool:
    try:
        return (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90.0 <= latitude <= 90.0
            and -180.0 <= longitude <= 180.0
        )
    except TypeError:
        return False


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS-84 points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True)
class LocationCheck:
    ok: bool
    reason: str  # OK | BAD_COORDINATES | LOW_ACCURACY | OUT_OF_RANGE
    distance_m: float | None


def check_location(
    site_lat: float,
    site_lon: float,
    radius_m: float,
    lat: float,
    lon: float,
    accuracy_m: float | None,
    max_accuracy_m: float,
) -> LocationCheck:
    if (
        not is_valid_coordinate(lat, lon)
        or accuracy_m is None
        or not math.isfinite(accuracy_m)
        or accuracy_m < 0
    ):
        return LocationCheck(False, "BAD_COORDINATES", None)
    distance = haversine_m(site_lat, site_lon, lat, lon)
    if accuracy_m > max_accuracy_m:
        return LocationCheck(False, "LOW_ACCURACY", distance)
    if distance > radius_m:
        return LocationCheck(False, "OUT_OF_RANGE", distance)
    return LocationCheck(True, "OK", distance)
