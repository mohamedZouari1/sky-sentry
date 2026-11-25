"""WMO weather codes and daily weather alerts."""
from __future__ import annotations

# WMO code -> (label, day icon, night icon)
WMO = {
    0: ("Clear sky", "☀️", "🌙"),
    1: ("Mostly clear", "🌤️", "🌙"),
    2: ("Partly cloudy", "⛅", "☁️"),
    3: ("Overcast", "☁️", "☁️"),
    45: ("Fog", "🌫️", "🌫️"),
    48: ("Freezing fog", "🌫️", "🌫️"),
    51: ("Light drizzle", "🌦️", "🌧️"),
    53: ("Drizzle", "🌦️", "🌧️"),
    55: ("Heavy drizzle", "🌧️", "🌧️"),
    56: ("Freezing drizzle", "🌧️", "🌧️"),
    57: ("Freezing drizzle", "🌧️", "🌧️"),
    61: ("Light rain", "🌦️", "🌧️"),
    63: ("Rain", "🌧️", "🌧️"),
    65: ("Heavy rain", "🌧️", "🌧️"),
    66: ("Freezing rain", "🌧️", "🌧️"),
    67: ("Freezing rain", "🌧️", "🌧️"),
    71: ("Light snow", "🌨️", "🌨️"),
    73: ("Snow", "🌨️", "🌨️"),
    75: ("Heavy snow", "❄️", "❄️"),
    77: ("Snow grains", "🌨️", "🌨️"),
    80: ("Rain showers", "🌦️", "🌧️"),
    81: ("Rain showers", "🌧️", "🌧️"),
    82: ("Violent showers", "⛈️", "⛈️"),
    85: ("Snow showers", "🌨️", "🌨️"),
    86: ("Heavy snow showers", "❄️", "❄️"),
    95: ("Thunderstorm", "⛈️", "⛈️"),
    96: ("Thunderstorm with hail", "⛈️", "⛈️"),
    99: ("Thunderstorm with hail", "⛈️", "⛈️"),
}


def describe(code, is_day: bool = True) -> dict:
    label, day, night = WMO.get(code, ("Unknown", "🌡️", "🌡️"))
    return {"code": code, "label": label, "icon": day if is_day else night}


def daily_alerts(tmax, tmin, precip_sum, precip_prob, wind_max, uv_max) -> list[dict]:
    """Short, human alerts for one forecast day (most important first)."""
    alerts = []
    if tmax is not None and tmax >= 35:
        alerts.append({"level": "danger", "icon": "🔥", "text": "Extreme heat"})
    elif tmax is not None and tmax >= 30:
        alerts.append({"level": "warn", "icon": "🥵", "text": "Hot day"})
    if tmin is not None and tmin <= 0:
        alerts.append({"level": "warn", "icon": "🧊", "text": "Freezing"})
    if (precip_sum or 0) >= 15:
        alerts.append({"level": "danger", "icon": "🌊", "text": "Heavy rain"})
    elif (precip_prob or 0) >= 60 or (precip_sum or 0) >= 3:
        alerts.append({"level": "info", "icon": "☔", "text": "Bring an umbrella"})
    if (wind_max or 0) >= 50:
        alerts.append({"level": "danger", "icon": "🌪️", "text": "Strong winds"})
    elif (wind_max or 0) >= 30:
        alerts.append({"level": "info", "icon": "💨", "text": "Windy"})
    if (uv_max or 0) >= 8:
        alerts.append({"level": "warn", "icon": "🕶️", "text": "Very high UV"})
    return alerts
