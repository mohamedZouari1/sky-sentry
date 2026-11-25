"""Builds the JSON payloads served by the API from raw Open-Meteo responses."""
from __future__ import annotations

from . import aqi as aqi_mod
from . import insights, openmeteo
from . import weather as wx_mod
from .cities import FEATURED_CITIES


def _at(series: dict, key: str, index: int):
    values = series.get(key) or []
    return values[index] if 0 <= index < len(values) else None


def conditions(lat: float, lon: float, sensitive: bool = False) -> dict:
    air = openmeteo.air_quality(lat, lon)
    wx = openmeteo.weather(lat, lon)
    hist = openmeteo.history(lat, lon)

    # ---- air -------------------------------------------------------------
    a_now = air.get("current", {})
    us_aqi = a_now.get("us_aqi")
    us_aqi = round(us_aqi) if isinstance(us_aqi, (int, float)) else None
    level = aqi_mod.level_for(us_aqi)
    breakdown = aqi_mod.pollutant_breakdown(a_now)
    dominant = aqi_mod.dominant_pollutant(breakdown)
    a_hourly = air.get("hourly", {})
    now_iso = a_now.get("time") or wx.get("current", {}).get("time", "")
    upcoming = [i for i, t in enumerate(a_hourly.get("time", [])) if t[:13] >= now_iso[:13]]
    forecast = []
    for i in upcoming:
        value = _at(a_hourly, "us_aqi", i)
        if value is None:
            continue
        lvl = aqi_mod.level_for(value)
        forecast.append({"time": a_hourly["time"][i], "aqi": round(value), "color": lvl["color"], "label": lvl["label"]})

    # ---- weather -----------------------------------------------------------
    w_now = wx.get("current", {})
    w_hourly = wx.get("hourly", {})
    daily = wx.get("daily", {})
    hour_index = next((i for i, t in enumerate(w_hourly.get("time", [])) if t[:13] == (w_now.get("time") or "")[:13]), -1)
    is_day = bool(w_now.get("is_day", 1))
    now_wx = {
        "temperature": w_now.get("temperature_2m"),
        "feels_like": w_now.get("apparent_temperature"),
        "humidity": w_now.get("relative_humidity_2m"),
        "wind": w_now.get("wind_speed_10m"),
        "wind_direction": w_now.get("wind_direction_10m"),
        "precipitation": w_now.get("precipitation"),
        "precip_prob": _at(w_hourly, "precipitation_probability", hour_index),
        "uv": w_now.get("uv_index"),
        "is_day": is_day,
        **wx_mod.describe(w_now.get("weather_code"), is_day),
    }
    days = []
    for i, date in enumerate(daily.get("time", [])):
        tmax, tmin = _at(daily, "temperature_2m_max", i), _at(daily, "temperature_2m_min", i)
        psum, pprob = _at(daily, "precipitation_sum", i), _at(daily, "precipitation_probability_max", i)
        wind, uv = _at(daily, "wind_speed_10m_max", i), _at(daily, "uv_index_max", i)
        days.append({
            "date": date, "tmax": tmax, "tmin": tmin, "precip_sum": psum, "precip_prob": pprob,
            "wind_max": wind, "uv_max": uv,
            "sunrise": _at(daily, "sunrise", i), "sunset": _at(daily, "sunset", i),
            **wx_mod.describe(_at(daily, "weather_code", i)),
            "alerts": wx_mod.daily_alerts(tmax, tmin, psum, pprob, wind, uv),
        })
    next_hours = []
    if hour_index >= 0:
        for i in range(hour_index, min(hour_index + 24, len(w_hourly.get("time", [])))):
            next_hours.append({
                "time": w_hourly["time"][i],
                "temperature": _at(w_hourly, "temperature_2m", i),
                "precip_prob": _at(w_hourly, "precipitation_probability", i),
                **wx_mod.describe(_at(w_hourly, "weather_code", i), bool(_at(w_hourly, "is_day", i) if _at(w_hourly, "is_day", i) is not None else 1)),
            })

    h_daily = hist.get("daily", {})
    history = {
        "dates": h_daily.get("time", []),
        "tmax": h_daily.get("temperature_2m_max", []),
        "tmin": h_daily.get("temperature_2m_min", []),
        "precip": h_daily.get("precipitation_sum", []),
    }

    return {
        "location": {"lat": lat, "lon": lon, "timezone": air.get("timezone") or wx.get("timezone"),
                     "local_time": now_iso},
        "air": {
            "aqi": us_aqi, "level": level,
            "dominant": dominant["key"] if dominant else None,
            "pollutants": breakdown,
            "forecast": forecast,
            "tips": aqi_mod.health_tips(us_aqi, dominant, sensitive),
        },
        "weather": {"now": now_wx, "daily": days, "hourly": next_hours},
        "history": history,
        "insights": {
            "verdict": insights.verdict(us_aqi, now_wx, sensitive),
            "activities": insights.activities(us_aqi, now_wx, sensitive),
            "best_window": insights.best_window(a_hourly, w_hourly, now_iso),
        },
        "sensitive": sensitive,
        "sources": ["Open-Meteo Air Quality API (CAMS)", "Open-Meteo Weather Forecast API"],
    }


def overview() -> list[dict]:
    points = [(c["lat"], c["lon"]) for c in FEATURED_CITIES]
    air, wx = openmeteo.overview(points)
    out = []
    for city, a, w in zip(FEATURED_CITIES, air, wx):
        value = (a.get("current") or {}).get("us_aqi")
        value = round(value) if isinstance(value, (int, float)) else None
        level = aqi_mod.level_for(value)
        cur = w.get("current") or {}
        sky = wx_mod.describe(cur.get("weather_code"), bool(cur.get("is_day", 1)))
        out.append({**city, "aqi": value, "color": level["color"], "label": level["label"],
                    "mascot": level["mascot"], "temperature": cur.get("temperature_2m"),
                    "weather": sky["label"], "icon": sky["icon"]})
    return out
