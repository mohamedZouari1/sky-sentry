"""Offline tests: external APIs are mocked, so no keys or network are needed."""
from unittest.mock import MagicMock, patch

import pytest

from skysentry import air_quality, create_app, weather
from skysentry.config import Config


@pytest.fixture
def client():
    return create_app().test_client()


def fake_response(payload, status=200):
    resp = MagicMock(status_code=status)
    resp.json.return_value = payload
    return resp


WAQI_OK = {
    "status": "ok",
    "data": {
        "aqi": 72,
        "dominentpol": "pm25",
        "city": {"name": "Chicago"},
        "iaqi": {"pm25": {"v": 72}, "o3": {"v": 21}},
        "time": {"s": "2025-10-05 12:00:00"},
    },
}


def test_pages_render(client):
    for path in ("/", "/weather"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert b"SKY SENTRY" in resp.data


def test_status(client):
    body = client.get("/api/status").get_json()
    assert body["status"] == "online"
    assert body["cities"] == 12


@pytest.mark.parametrize("aqi,level", [(10, "Good"), (75, "Moderate"), (120, "Unhealthy for Sensitive Groups"),
                                       (180, "Unhealthy"), (250, "Very Unhealthy"), (400, "Hazardous")])
def test_aqi_scale(aqi, level):
    assert air_quality.get_aqi_info(aqi)["level"] == level


def test_air_quality_success(client, monkeypatch):
    monkeypatch.setattr(Config, "WAQI_API_TOKEN", "test-token")
    with patch("skysentry.air_quality.requests.get", return_value=fake_response(WAQI_OK)) as get:
        body = client.get("/api/air-quality/chicago").get_json()
    assert get.call_args.kwargs["params"] == {"token": "test-token"}
    assert body["aqi"] == 72
    assert body["aqi_level"] == "Moderate"
    assert body["has_real_data"] is True
    assert any("HEPA" in r for r in body["recommendations"])


def test_air_quality_station_without_reading(client, monkeypatch):
    monkeypatch.setattr(Config, "WAQI_API_TOKEN", "test-token")
    payload = {"status": "ok", "data": {**WAQI_OK["data"], "aqi": "-"}}
    with patch("skysentry.air_quality.requests.get", return_value=fake_response(payload)):
        body = client.get("/api/air-quality/chicago").get_json()
    assert body["aqi"] == "No Data"
    assert body["has_real_data"] is False


def test_air_quality_without_token_returns_no_data(client, monkeypatch):
    monkeypatch.setattr(Config, "WAQI_API_TOKEN", "")
    body = client.get("/api/air-quality/boston").get_json()
    assert body["has_real_data"] is False


@pytest.mark.parametrize("path", ["/api/air-quality/atlantis", "/api/historical/atlantis",
                                  "/api/weather/forecast/atlantis"])
def test_unknown_city(client, path):
    assert client.get(path).status_code == 404


def test_weather_forecast_falls_back_without_credentials(client, monkeypatch):
    monkeypatch.setattr(Config, "METEOMATICS_USERNAME", "")
    monkeypatch.setattr(Config, "METEOMATICS_PASSWORD", "")
    with patch("skysentry.weather.requests.get", return_value=fake_response({}, status=401)):
        body = client.get("/api/weather/forecast/seattle").get_json()
    assert len(body["dates"]) == len(body["temperatures"]) == len(body["precipitation"]) == len(body["windSpeed"])
    assert body["weather_alerts"], "forecast view should include daily alerts"
    assert body["data_quality"] == "simulated_fallback"


def test_weather_icon_and_alerts():
    assert weather.get_weather_icon(20, 20, 3) == "🌧️"
    assert weather.get_weather_icon(38, 0, 3) == "🔥"
    assert "Extreme Heat Warning" in weather.get_weather_alert(38, 0, 0)
