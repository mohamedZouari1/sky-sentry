"""Offline tests: Open-Meteo is mocked, so no network is needed."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from skysentry import aqi, create_app, insights, openmeteo, weather
from skysentry.cities import FEATURED_CITIES

HOURS = [f"2025-10-05T{h:02d}:00" for h in range(24)] + [f"2025-10-06T{h:02d}:00" for h in range(24)]
DAYS = [f"2025-10-{d:02d}" for d in range(5, 12)]


def fake_air(lat, lon):
    return {
        "timezone": "America/Chicago",
        "current": {"time": "2025-10-05T09:00", "us_aqi": 72, "pm2_5": 24.0, "pm10": 30.0, "ozone": 60.0,
                    "nitrogen_dioxide": 12.0, "sulphur_dioxide": 3.0, "carbon_monoxide": 200.0},
        # cleanest air at 15:00-16:00 on day one
        "hourly": {"time": HOURS, "us_aqi": [20 if h in ("2025-10-05T15:00", "2025-10-05T16:00") else 80 for h in HOURS]},
    }


def fake_weather(lat, lon):
    return {
        "timezone": "America/Chicago",
        "current": {"time": "2025-10-05T09:00", "temperature_2m": 21.0, "apparent_temperature": 22.0,
                    "relative_humidity_2m": 55, "weather_code": 2, "wind_speed_10m": 12.0, "wind_direction_10m": 200,
                    "precipitation": 0.0, "is_day": 1, "uv_index": 4.0},
        "hourly": {"time": HOURS, "temperature_2m": [20.0] * 48, "apparent_temperature": [20.0] * 48,
                   "precipitation_probability": [10] * 48, "weather_code": [1] * 48, "uv_index": [3.0] * 48,
                   "is_day": [1 if 7 <= int(h[11:13]) <= 18 else 0 for h in HOURS]},
        "daily": {"time": DAYS, "weather_code": [0, 61, 95, 3, 2, 1, 0],
                  "temperature_2m_max": [24, 36, 22, 20, 18, 19, 21], "temperature_2m_min": [12, 20, 10, -2, 8, 9, 10],
                  "precipitation_sum": [0, 0, 20, 0, 0, 1, 0], "precipitation_probability_max": [5, 10, 90, 5, 0, 30, 0],
                  "wind_speed_10m_max": [10, 15, 55, 20, 10, 10, 10], "uv_index_max": [5, 9, 2, 3, 4, 4, 5],
                  "sunrise": [f"{d}T07:00" for d in DAYS], "sunset": [f"{d}T18:30" for d in DAYS]},
    }


def fake_history(lat, lon, days=30):
    return {"daily": {"time": DAYS, "temperature_2m_max": [20] * 7, "temperature_2m_min": [10] * 7,
                      "precipitation_sum": [0] * 7}}


@pytest.fixture
def client():
    openmeteo.clear_cache()
    with patch.object(openmeteo, "air_quality", fake_air), patch.object(openmeteo, "weather", fake_weather), \
            patch.object(openmeteo, "history", fake_history):
        yield create_app().test_client()


# ---------- pages & simple endpoints ----------

def test_index_and_assets(client):
    page = client.get("/")
    assert page.status_code == 200 and b"SkySentry" in page.data
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/static/css/app.css").status_code == 200


def test_status_and_cities(client):
    assert client.get("/api/status").get_json()["status"] == "online"
    assert len(client.get("/api/cities").get_json()) == len(FEATURED_CITIES)
    assert len(client.get("/api/scale").get_json()["levels"]) == 6


# ---------- conditions ----------

def test_conditions_payload(client):
    body = client.get("/api/conditions?lat=41.88&lon=-87.63").get_json()
    assert body["air"]["aqi"] == 72
    assert body["air"]["level"]["label"] == "Moderate"
    assert body["air"]["dominant"] == "pm2_5"          # 24 / 15 is the highest WHO ratio
    assert body["air"]["forecast"][0]["time"] == "2025-10-05T09:00"
    assert body["weather"]["now"]["label"] == "Partly cloudy"
    assert len(body["weather"]["daily"]) == 7
    assert len(body["weather"]["hourly"]) == 24
    assert {a["key"] for a in body["insights"]["activities"]} == {"run", "bike", "kids", "walk", "windows", "laundry"}


def test_best_window_picks_cleanest_daylight_slot(client):
    bw = client.get("/api/conditions?lat=41.88&lon=-87.63").get_json()["insights"]["best_window"]
    assert bw["start"] == "2025-10-05T15:00"
    assert bw["aqi"] == 20 and bw["day"] == "Today"


def test_daily_alerts_in_payload(client):
    days = client.get("/api/conditions?lat=41.88&lon=-87.63").get_json()["weather"]["daily"]
    texts = lambda i: {a["text"] for a in days[i]["alerts"]}  # noqa: E731
    assert "Extreme heat" in texts(1) and "Very high UV" in texts(1)
    assert {"Heavy rain", "Strong winds"} <= texts(2)
    assert "Freezing" in texts(3)


def test_sensitive_mode_is_stricter(client):
    normal = client.get("/api/conditions?lat=41.88&lon=-87.63").get_json()["insights"]["activities"]
    strict = client.get("/api/conditions?lat=41.88&lon=-87.63&sensitive=1").get_json()["insights"]["activities"]
    run = lambda acts: next(a for a in acts if a["key"] == "run")["status"]  # noqa: E731
    assert run(normal) == "go" and run(strict) == "caution"


@pytest.mark.parametrize("qs", ["", "lat=abc&lon=1", "lat=91&lon=0", "lat=0&lon=181"])
def test_conditions_rejects_bad_coordinates(client, qs):
    assert client.get(f"/api/conditions?{qs}").status_code == 400


def test_upstream_failure_returns_502():
    openmeteo.clear_cache()
    with patch.object(openmeteo._session, "get", side_effect=requests.ConnectionError("offline")):
        resp = create_app().test_client().get("/api/conditions?lat=1&lon=1")
    assert resp.status_code == 502 and "error" in resp.get_json()


# ---------- search & overview ----------

def test_search(client):
    results = [{"name": "Sfax", "country": "Tunisia", "admin1": "Sfax", "latitude": 34.74, "longitude": 10.76}]
    with patch.object(openmeteo, "search", return_value=results):
        body = client.get("/api/search?q=sfax").get_json()
    assert body == [{"name": "Sfax", "country": "Tunisia", "admin1": "Sfax", "country_code": None, "lat": 34.74, "lon": 10.76}]
    assert client.get("/api/search?q=a").get_json() == []


def test_overview_batches_all_cities(client):
    n = len(FEATURED_CITIES)
    air = [{"current": {"us_aqi": 30 + i}} for i in range(n)]
    wx = [{"current": {"temperature_2m": 15.0, "weather_code": 0, "is_day": 1}} for _ in range(n)]
    with patch.object(openmeteo, "overview", return_value=(air, wx)) as ov:
        body = client.get("/api/overview").get_json()
    assert ov.call_count == 1
    assert body[0]["aqi"] == 30 and body[0]["label"] == "Good" and body[0]["weather"] == "Clear sky"


def test_client_caches_responses():
    openmeteo.clear_cache()
    resp = MagicMock()
    resp.json.return_value = {"results": []}
    with patch.object(openmeteo._session, "get", return_value=resp) as get:
        openmeteo.search("Paris")
        openmeteo.search("Paris")
    assert get.call_count == 1


# ---------- pure logic ----------

@pytest.mark.parametrize("value,label", [(10, "Good"), (75, "Moderate"), (120, "Unhealthy for Sensitive Groups"),
                                         (180, "Unhealthy"), (250, "Very Unhealthy"), (400, "Hazardous"), (None, "No data")])
def test_aqi_levels(value, label):
    assert aqi.level_for(value)["label"] == label


def test_air_status_thresholds():
    assert insights.air_status(90, sensitive=False)[0] == "go"
    assert insights.air_status(90, sensitive=True)[0] == "caution"
    assert insights.air_status(160, sensitive=False)[0] == "avoid"
    assert insights.air_status(160, sensitive=False, shift=1)[0] == "caution"


def test_verdicts():
    assert insights.verdict(20, {"feels_like": 20}, False)["title"] == "Great day to be outside!"
    assert insights.verdict(130, {"feels_like": 20}, False)["status"] == "caution"
    assert insights.verdict(30, {"feels_like": 40}, False)["status"] == "avoid"


def test_weather_codes():
    assert weather.describe(0, True)["icon"] == "☀️"
    assert weather.describe(0, False)["icon"] == "🌙"
    assert weather.describe(1234)["label"] == "Unknown"
