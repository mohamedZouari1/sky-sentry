"""Quick CLI check of live AQI for every monitored city.

Usage:  python scripts/check_waqi.py   (needs WAQI_API_TOKEN in your env or .env)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skysentry.air_quality import get_realtime_air_quality  # noqa: E402
from skysentry.cities import CITIES  # noqa: E402
from skysentry.config import Config  # noqa: E402


def main() -> int:
    if not Config.WAQI_API_TOKEN:
        print("❌ WAQI_API_TOKEN is not set. Copy .env.example to .env and add your token.")
        return 1
    print(f"{'City':<16}{'AQI':>6}  {'Level':<32}Dominant")
    print("-" * 66)
    for key in CITIES:
        d = get_realtime_air_quality(key)
        print(f"{d['city_display'][:15]:<16}{str(d['aqi']):>6}  {d['aqi_level']:<32}{d['dominant_pollutant']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
