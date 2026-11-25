"""Print a live air quality snapshot for every featured city, right in your terminal.

Usage:  python scripts/air_report.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skysentry.report import overview  # noqa: E402


def main() -> int:
    for stream in (sys.stdout,):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    rows = sorted(overview(), key=lambda c: (c["aqi"] is None, c["aqi"] or 0))
    print(f"\n  {'City':<14}{'AQI':>5}   {'Level':<32}{'Weather'}")
    print("  " + "-" * 70)
    for c in rows:
        temp = f"{c['temperature']:.0f}°C" if c["temperature"] is not None else "--"
        print(f"  {c['name']:<14}{str(c['aqi'] or '--'):>5}   {c['mascot']} {c['label']:<30}{c['icon']} {temp}")
    print("\n  Data: Open-Meteo.com (CC BY 4.0)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
