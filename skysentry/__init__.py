"""SkySentry - real-time air quality & weather protection platform.

Built for the NASA Space Apps Challenge 2025.
"""
import logging
import sys
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from .cities import CITIES
from .config import Config

__version__ = "1.0.0"

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> Flask:
    """Application factory: one server for both dashboards and their APIs."""
    from . import air_quality, weather

    # Emoji-friendly console output on Windows (cp1252) terminals
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__, static_folder=None)
    app.register_blueprint(air_quality.bp)
    app.register_blueprint(weather.bp)

    @app.route("/")
    def air_quality_page():
        return send_from_directory(STATIC_DIR, "air-quality.html")

    @app.route("/weather")
    def weather_page():
        return send_from_directory(STATIC_DIR, "weather.html")

    @app.route("/api/status")
    def status():
        return jsonify(
            {
                "status": "online",
                "service": "SkySentry",
                "version": __version__,
                "cities": len(CITIES),
                "integrations": {
                    "waqi": bool(Config.WAQI_API_TOKEN),
                    "meteomatics": bool(Config.METEOMATICS_USERNAME and Config.METEOMATICS_PASSWORD),
                },
            }
        )

    @app.route("/api/cities")
    def cities():
        return jsonify(CITIES)

    return app
