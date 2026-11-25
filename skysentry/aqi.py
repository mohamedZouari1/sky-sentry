"""US EPA Air Quality Index scale, pollutant facts and health guidance."""
from __future__ import annotations

# Upper bound (inclusive) of each US AQI band
LEVELS = [
    {"max": 50, "key": "good", "label": "Good", "color": "#22c55e", "mascot": "😄",
     "summary": "Air is clean and fresh. Enjoy it!",
     "advice": "A perfect day to be outside."},
    {"max": 100, "key": "moderate", "label": "Moderate", "color": "#eab308", "mascot": "🙂",
     "summary": "Air is acceptable for almost everyone.",
     "advice": "Unusually sensitive people should ease off long, hard workouts."},
    {"max": 150, "key": "usg", "label": "Unhealthy for Sensitive Groups", "color": "#f97316", "mascot": "😐",
     "summary": "Sensitive people may start to feel it.",
     "advice": "Kids, older adults and people with asthma or heart disease should cut back outdoor exertion."},
    {"max": 200, "key": "unhealthy", "label": "Unhealthy", "color": "#ef4444", "mascot": "😷",
     "summary": "Everyone may begin to feel health effects.",
     "advice": "Keep outdoor activity short and light. Sensitive groups should stay inside."},
    {"max": 300, "key": "very_unhealthy", "label": "Very Unhealthy", "color": "#a855f7", "mascot": "🤢",
     "summary": "Health alert: serious effects are possible for everyone.",
     "advice": "Avoid outdoor exertion. Close windows and run an air purifier if you have one."},
    {"max": 10_000, "key": "hazardous", "label": "Hazardous", "color": "#9f1239", "mascot": "☠️",
     "summary": "Emergency conditions for the whole population.",
     "advice": "Stay indoors with windows shut. Wear an N95 mask if you must go out."},
]

UNKNOWN_LEVEL = {"max": None, "key": "unknown", "label": "No data", "color": "#94a3b8", "mascot": "🤔",
                 "summary": "No air quality reading is available right now.",
                 "advice": "Check back in a little while."}

# WHO 2021 air quality guidelines (24-hour means, ozone is the 8-hour peak), in µg/m³
POLLUTANTS = {
    "pm2_5": {"name": "PM2.5", "full": "Fine particles", "who": 15,
              "what": "Tiny particles 30x thinner than a hair that reach deep into the lungs and blood.",
              "sources": "Traffic, wood burning, industry, wildfire smoke"},
    "pm10": {"name": "PM10", "full": "Coarse particles", "who": 45,
             "what": "Dust and pollen-sized particles that irritate the nose, throat and lungs.",
             "sources": "Road dust, construction, desert dust, pollen"},
    "ozone": {"name": "O₃", "full": "Ozone", "who": 100,
              "what": "A gas formed when sunlight cooks traffic fumes. It peaks on sunny afternoons.",
              "sources": "Sunlight + vehicle and industrial emissions"},
    "nitrogen_dioxide": {"name": "NO₂", "full": "Nitrogen dioxide", "who": 25,
                         "what": "A reddish traffic gas that inflames airways and worsens asthma.",
                         "sources": "Cars, trucks, gas stoves, power plants"},
    "sulphur_dioxide": {"name": "SO₂", "full": "Sulphur dioxide", "who": 40,
                        "what": "A sharp-smelling gas that tightens airways within minutes.",
                        "sources": "Coal and oil burning, ships, volcanoes"},
    "carbon_monoxide": {"name": "CO", "full": "Carbon monoxide", "who": 4000,
                        "what": "An invisible, odourless gas that reduces oxygen in the blood.",
                        "sources": "Exhaust, incomplete burning, heaters"},
}

POLLUTANT_TIPS = {
    "pm2_5": "Fine particles dominate: an air purifier with a HEPA filter helps indoors, and an N95 mask helps outside.",
    "pm10": "Dust is the main issue: keep windows closed on windy days and wipe surfaces with a damp cloth.",
    "ozone": "Ozone dominates: it is lowest in the morning, so plan workouts early and skip sunny afternoons.",
    "nitrogen_dioxide": "Traffic fumes dominate: choose routes through parks and away from busy roads.",
    "sulphur_dioxide": "SO₂ is elevated: people with asthma should keep their inhaler close.",
    "carbon_monoxide": "CO is elevated: make sure indoor heaters and stoves are well ventilated.",
}


def level_for(aqi) -> dict:
    if aqi is None:
        return dict(UNKNOWN_LEVEL)
    for level in LEVELS:
        if aqi <= level["max"]:
            return dict(level)
    return dict(LEVELS[-1])


def pollutant_breakdown(current: dict) -> list[dict]:
    """Each pollutant's value compared with its WHO guideline."""
    out = []
    for key, info in POLLUTANTS.items():
        value = current.get(key)
        ratio = round(value / info["who"], 2) if isinstance(value, (int, float)) else None
        out.append({"key": key, **info, "value": value, "unit": "µg/m³", "ratio": ratio})
    return out


def dominant_pollutant(breakdown: list[dict]) -> dict | None:
    ranked = [p for p in breakdown if p["ratio"] is not None]
    return max(ranked, key=lambda p: p["ratio"]) if ranked else None


def health_tips(aqi, dominant: dict | None, sensitive: bool) -> list[str]:
    level = level_for(aqi)
    tips = [level["advice"]]
    if dominant and dominant["ratio"] and dominant["ratio"] > 1:
        tips.append(POLLUTANT_TIPS[dominant["key"]])
    if aqi is not None:
        if sensitive and aqi > 50:
            tips.append("Sensitive mode: keep any rescue medication with you and take breaks indoors.")
        if aqi > 100:
            tips.append("Close windows during the worst hours, then air out the home when the AQI drops.")
        if aqi <= 50:
            tips.append("Open the windows for a while to let fresh air into your home.")
    return tips
