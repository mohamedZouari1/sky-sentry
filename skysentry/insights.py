"""Turns raw numbers into decisions: activity advice, a daily verdict and the best time outside."""
from __future__ import annotations

from datetime import datetime

GO, CAUTION, AVOID = "go", "caution", "avoid"
_RANK = {GO: 0, CAUTION: 1, AVOID: 2}


def _worst(*items: tuple[str, str]) -> tuple[str, str]:
    """Pick the most severe (status, reason) pair."""
    return max(items, key=lambda i: _RANK[i[0]])


def air_status(aqi, sensitive: bool, shift: int = 0) -> tuple[str, str]:
    """EPA-style exertion guidance. `shift` relaxes (+) or tightens (-) the thresholds by whole bands."""
    if aqi is None:
        return GO, "No air reading available right now"
    bands = [50, 100, 150, 200, 300]
    caution_at = bands[max(0, min(4, (0 if sensitive else 1) + shift))]
    avoid_at = bands[max(0, min(4, (1 if sensitive else 2) + shift))]
    if aqi > avoid_at:
        return AVOID, f"AQI {aqi} is too high for this"
    if aqi > caution_at:
        return CAUTION, f"AQI {aqi}: keep it short and easy"
    return GO, "Air quality is fine"


def heat_status(feels) -> tuple[str, str]:
    if feels is None:
        return GO, ""
    if feels >= 38:
        return AVOID, f"Dangerous heat (feels like {feels:.0f}°C)"
    if feels >= 32:
        return CAUTION, f"Hot (feels like {feels:.0f}°C): hydrate and seek shade"
    if feels <= -10:
        return CAUTION, f"Bitter cold (feels like {feels:.0f}°C): dress in layers"
    return GO, ""


def rain_status(precip_now, precip_prob) -> tuple[str, str]:
    if (precip_now or 0) >= 1:
        return CAUTION, "It is raining right now"
    if (precip_prob or 0) >= 70:
        return CAUTION, f"{precip_prob}% chance of rain"
    return GO, ""


def activities(aqi, wx: dict, sensitive: bool) -> list[dict]:
    """Go / caution / avoid for everyday activities, with the main reason."""
    feels = wx.get("feels_like")
    wind = wx.get("wind") or 0
    uv = wx.get("uv") or 0
    humidity = wx.get("humidity") or 0
    rain = rain_status(wx.get("precipitation"), wx.get("precip_prob"))
    heat = heat_status(feels)
    wind_s = (AVOID, "Gale-force wind") if wind >= 50 else (CAUTION, f"Windy ({wind:.0f} km/h)") if wind >= 30 else (GO, "")
    uv_s = (CAUTION, f"UV {uv:.0f}: sunscreen and a hat") if uv >= 8 else (GO, "")

    def item(key, icon, name, *checks):
        status, reason = _worst(*checks)
        return {"key": key, "icon": icon, "name": name, "status": status,
                "reason": reason or "Conditions look great"}

    v_status, _ = air_status(aqi, sensitive=True)
    ventilate = (v_status, {GO: "Let the fresh air in",
                            CAUTION: "Air out briefly, then close up",
                            AVOID: "Keep windows shut for now"}[v_status])
    laundry_rain = (AVOID, "Rain is likely") if (wx.get("precip_prob") or 0) >= 60 or (wx.get("precipitation") or 0) > 0 \
        else (CAUTION, "Very humid, so it will dry slowly") if humidity >= 85 else (GO, "")

    return [
        item("run", "🏃", "Running", air_status(aqi, sensitive), heat, rain),
        item("bike", "🚴", "Cycling", air_status(aqi, sensitive), heat, rain, wind_s),
        item("kids", "🧒", "Kids outside", air_status(aqi, sensitive=True), heat, rain, uv_s),
        item("walk", "🚶", "Walk & errands", air_status(aqi, sensitive, shift=1), heat),
        item("windows", "🪟", "Open windows", ventilate),
        item("laundry", "🧺", "Dry laundry outside", laundry_rain, air_status(aqi, sensitive, shift=1)),
    ]


def verdict(aqi, wx: dict, sensitive: bool) -> dict:
    status, _ = _worst(air_status(aqi, sensitive), heat_status(wx.get("feels_like")))
    if aqi is None:
        return {"status": GO, "title": "Air data is on its way", "text": "We could not get a reading yet."}
    if status == GO and aqi <= 50:
        return {"status": GO, "title": "Great day to be outside!", "text": "Clean air. Go enjoy it."}
    if status == GO:
        return {"status": GO, "title": "Good to go", "text": "Air is acceptable for normal outdoor plans."}
    if status == CAUTION:
        return {"status": CAUTION, "title": "Take it easy outside",
                "text": "Shorter, lighter activity is the smart move today."}
    return {"status": AVOID, "title": "Better to stay inside",
            "text": "Limit time outdoors and keep windows closed."}


def _discomfort(feels) -> float:
    if feels is None:
        return 0.0
    return max(0.0, feels - 26) * 3 + max(0.0, 8 - feels) * 2


def best_window(air_hourly: dict, wx_hourly: dict, now_iso: str, hours: int = 36, span: int = 2) -> dict | None:
    """Best `span`-hour daylight slot in the next `hours`, weighing AQI, rain and comfort."""
    if not now_iso:
        return None
    now_hour = now_iso[:13]
    a_times = air_hourly.get("time", [])
    aqi_by_time = dict(zip(a_times, air_hourly.get("us_aqi", [])))
    w_times = wx_hourly.get("time", [])
    feels_by_time = dict(zip(w_times, wx_hourly.get("apparent_temperature", [])))
    rain_by_time = dict(zip(w_times, wx_hourly.get("precipitation_probability", [])))
    day_by_time = dict(zip(w_times, wx_hourly.get("is_day", [])))

    upcoming = [t for t in a_times if t[:13] >= now_hour][:hours]
    slots = []
    for t in upcoming:
        hour = int(t[11:13])
        aqi = aqi_by_time.get(t)
        daylight = day_by_time.get(t)
        is_daytime = bool(daylight) if daylight is not None else 6 <= hour <= 20
        if aqi is None or not is_daytime:
            continue
        feels, rain = feels_by_time.get(t), rain_by_time.get(t) or 0
        slots.append((t, aqi, feels, rain, aqi + rain * 0.6 + _discomfort(feels)))

    best = None
    for i in range(len(slots) - span + 1):
        group = slots[i:i + span]
        # must be consecutive hours
        if int(group[-1][0][11:13]) - int(group[0][0][11:13]) != span - 1:
            continue
        score = sum(s[4] for s in group) / span
        if best is None or score < best[0]:
            best = (score, group)
    if not best:
        return None
    group = best[1]
    start = datetime.fromisoformat(group[0][0])
    feels_vals = [s[2] for s in group if s[2] is not None]
    return {
        "start": group[0][0],
        "end_hour": int(group[-1][0][11:13]) + 1,
        "day": "Today" if group[0][0][:10] == now_iso[:10] else "Tomorrow",
        "start_hour": start.hour,
        "aqi": round(sum(s[1] for s in group) / span),
        "feels_like": round(sum(feels_vals) / len(feels_vals), 1) if feels_vals else None,
        "rain_chance": max(s[3] for s in group),
    }
