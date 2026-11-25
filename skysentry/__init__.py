"""SkySentry - know when the air is safe to breathe.

Real-time air quality, weather and health guidance for any city on Earth,
powered by the free Open-Meteo APIs. Built for the NASA Space Apps Challenge 2025.
"""
import logging
import sys

from flask import Flask, jsonify, request

from . import aqi, openmeteo, report
from .cities import FEATURED_CITIES

__version__ = "2.0.0"


def _coords():
    """Validated (lat, lon) from the query string, or None."""
    try:
        lat, lon = float(request.args["lat"]), float(request.args["lon"])
    except (KeyError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return round(lat, 3), round(lon, 3)


def create_app() -> Flask:
    """Application factory."""
    for stream in (sys.stdout, sys.stderr):  # emoji-safe output on Windows terminals
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.json.ensure_ascii = False

    @app.errorhandler(openmeteo.UpstreamError)
    def upstream_error(exc):
        app.logger.warning("Upstream error: %s", exc)
        return jsonify({"error": "The data provider is not responding. Please try again in a moment."}), 502

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    @app.route("/api/status")
    def status():
        return jsonify({"status": "online", "service": "SkySentry", "version": __version__,
                        "data_provider": "Open-Meteo (free, no API key)"})

    @app.route("/api/cities")
    def cities():
        return jsonify(FEATURED_CITIES)

    @app.route("/api/scale")
    def scale():
        return jsonify({"levels": aqi.LEVELS, "pollutants": aqi.POLLUTANTS})

    @app.route("/api/search")
    def search():
        query = (request.args.get("q") or "").strip()
        if len(query) < 2:
            return jsonify([])
        results = openmeteo.search(query)
        return jsonify([
            {"name": r.get("name"), "country": r.get("country"), "admin1": r.get("admin1"),
             "country_code": r.get("country_code"), "lat": r.get("latitude"), "lon": r.get("longitude")}
            for r in results if r.get("latitude") is not None
        ])

    @app.route("/api/conditions")
    def conditions():
        coords = _coords()
        if coords is None:
            return jsonify({"error": "Provide valid lat and lon query parameters."}), 400
        sensitive = request.args.get("sensitive") in ("1", "true", "yes")
        return jsonify(report.conditions(*coords, sensitive=sensitive))

    @app.route("/api/overview")
    def overview():
        return jsonify(report.overview())

    return app
