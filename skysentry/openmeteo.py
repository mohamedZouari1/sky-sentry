"""Thin, cached client for the free Open-Meteo APIs (no API key required).

* Air quality  - https://open-meteo.com/en/docs/air-quality-api  (CAMS models)
* Weather      - https://open-meteo.com/en/docs
* Geocoding    - https://open-meteo.com/en/docs/geocoding-api

Data by Open-Meteo.com, licensed under CC BY 4.0.
"""
from __future__ import annotations

import threading
import time

import requests

from .config import Config

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

POLLUTANT_VARS = "pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide"

_session = requests.Session()
_session.headers["User-Agent"] = "SkySentry/2.0"
_cache: dict[tuple, tuple[float, object]] = {}
_lock = threading.Lock()


class UpstreamError(RuntimeError):
    """Raised when Open-Meteo is unreachable or returns an error."""


def _get(url: str, params: dict) -> object:
    key = (url, tuple(sorted(params.items())))
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < Config.CACHE_SECONDS:
            return hit[1]
    try:
        resp = _session.get(url, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstreamError(f"Open-Meteo request failed: {exc}") from exc
    if isinstance(data, dict) and data.get("error"):
        raise UpstreamError(data.get("reason", "Open-Meteo returned an error"))
    with _lock:
        if len(_cache) > 512:  # keep memory bounded
            _cache.clear()
        _cache[key] = (now, data)
    return data


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def search(query: str, count: int = 6) -> list[dict]:
    data = _get(GEOCODE_URL, {"name": query, "count": count, "format": "json", "language": "en"})
    return data.get("results", []) if isinstance(data, dict) else []


def air_quality(lat: float, lon: float) -> dict:
    return _get(AIR_URL, {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 5,
        "current": f"us_aqi,{POLLUTANT_VARS}",
        "hourly": f"us_aqi,{POLLUTANT_VARS}",
    })


def weather(lat: float, lon: float) -> dict:
    return _get(WEATHER_URL, {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 7,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
                   "wind_speed_10m,wind_direction_10m,precipitation,is_day,uv_index",
        "hourly": "temperature_2m,apparent_temperature,precipitation_probability,weather_code,uv_index,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,wind_speed_10m_max,uv_index_max,sunrise,sunset",
    })


def history(lat: float, lon: float, days: int = 30) -> dict:
    return _get(WEATHER_URL, {
        "latitude": lat, "longitude": lon, "timezone": "auto", "past_days": days, "forecast_days": 1,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
    })


def overview(points: list[tuple[float, float]]) -> tuple[list[dict], list[dict]]:
    """Current AQI + weather for many locations in just two batched requests."""
    lats = ",".join(f"{p[0]}" for p in points)
    lons = ",".join(f"{p[1]}" for p in points)
    air = _get(AIR_URL, {"latitude": lats, "longitude": lons, "current": "us_aqi,pm2_5", "timezone": "auto"})
    wx = _get(WEATHER_URL, {"latitude": lats, "longitude": lons,
                            "current": "temperature_2m,weather_code,is_day", "timezone": "auto"})
    as_list = lambda d: d if isinstance(d, list) else [d]  # noqa: E731
    return as_list(air), as_list(wx)
