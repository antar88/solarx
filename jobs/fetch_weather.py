"""Fetch plane-of-array irradiance from Open-Meteo into the daily_weather rollup.

The Performance Ratio the dashboard shows is
    PR = energy_kwh / (system_kwp * poa_kwh_m2)
so we need the daily plane-of-array (tilted) insolation in kWh/m². Open-Meteo is free
and needs no API key.

Two data sources, picked by date:
  * archive API (ERA5 reanalysis) for days older than ~5 days — the accurate history;
  * forecast API (`past_days`) for the recent window, since ERA5 lags a few days.

Hourly irradiance (W/m²) is requested with timezone=auto so timestamps are local,
matching how inverter_data is bucketed by local day, then summed per day to kWh/m².

Usage:
    python -m jobs.fetch_weather                 # refresh the recent window (default)
    python -m jobs.fetch_weather --full          # backfill from FIRST_DAY to today
    python -m jobs.fetch_weather --start 2025-01-01 --end 2025-03-31
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta

import pymysql

# System geometry (see the project memory / DESIGN). Overridable via env.
LATITUDE = float(os.getenv("SOLARX_LAT", "41.559302"))
LONGITUDE = float(os.getenv("SOLARX_LON", "2.218637"))
TILT_DEG = float(os.getenv("SOLARX_TILT", "30"))
# Azimuth given as a compass bearing where 180 = due south. Open-Meteo wants
# 0 = south, negative = east, so we convert with (compass - 180).
AZIMUTH_COMPASS = float(os.getenv("SOLARX_AZIMUTH", "166"))

# Earliest day with inverter data worth fetching weather for.
FIRST_DAY = date(2024, 7, 5)
# ERA5 archive lags real time; anything more recent comes from the forecast API.
ARCHIVE_LAG_DAYS = 5

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_HOURLY_VARS = "global_tilted_irradiance,shortwave_radiation,temperature_2m"


def _open_meteo_azimuth() -> float:
    return AZIMUTH_COMPASS - 180.0


def daily_from_hourly(payload: dict) -> dict[date, tuple[float | None, float | None, float | None]]:
    """Aggregate Open-Meteo hourly arrays into per-local-day values.

    Returns {day: (poa_kwh_m2, ghi_kwh_m2, temp_avg)}. Irradiance is summed (each
    hourly W/m² sample covers one hour, so Σ W/m² over a day ÷ 1000 = kWh/m²);
    temperature is averaged. Missing samples (null) are skipped.
    """
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    gti = hourly.get("global_tilted_irradiance") or []
    ghi = hourly.get("shortwave_radiation") or []
    temp = hourly.get("temperature_2m") or []

    poa_sum: dict[date, float] = defaultdict(float)
    ghi_sum: dict[date, float] = defaultdict(float)
    temp_sum: dict[date, float] = defaultdict(float)
    temp_n: dict[date, int] = defaultdict(int)
    days: list[date] = []
    seen: set[date] = set()

    for i, t in enumerate(times):
        day = datetime.fromisoformat(t).date()
        if day not in seen:
            seen.add(day)
            days.append(day)
        if i < len(gti) and gti[i] is not None:
            poa_sum[day] += gti[i]
        if i < len(ghi) and ghi[i] is not None:
            ghi_sum[day] += ghi[i]
        if i < len(temp) and temp[i] is not None:
            temp_sum[day] += temp[i]
            temp_n[day] += 1

    out: dict[date, tuple[float | None, float | None, float | None]] = {}
    for day in days:
        poa = round(poa_sum[day] / 1000.0, 3) if day in poa_sum else None
        ghi_v = round(ghi_sum[day] / 1000.0, 3) if day in ghi_sum else None
        temp_avg = round(temp_sum[day] / temp_n[day], 2) if temp_n[day] else None
        out[day] = (poa, ghi_v, temp_avg)
    return out


def _fetch(base_url: str, extra: dict) -> dict:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": _HOURLY_VARS,
        "tilt": TILT_DEG,
        "azimuth": _open_meteo_azimuth(),
        "timezone": "auto",
        **extra,
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "solarx-dashboard"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        return json.loads(resp.read().decode())


def fetch_range(start: date, end: date) -> dict[date, tuple]:
    """Fetch daily weather for [start, end] inclusive, choosing archive vs forecast.

    Splits the request at the archive cutoff so old days use ERA5 and recent days use
    the forecast API's ``past_days`` window.
    """
    cutoff = date.today() - timedelta(days=ARCHIVE_LAG_DAYS)
    result: dict[date, tuple] = {}

    if start <= cutoff:
        arch_end = min(end, cutoff)
        payload = _fetch(
            ARCHIVE_URL,
            {"start_date": start.isoformat(), "end_date": arch_end.isoformat()},
        )
        result.update(daily_from_hourly(payload))

    if end > cutoff:
        # forecast API: past_days covers recent history, forecast_days=1 includes today.
        payload = _fetch(
            FORECAST_URL,
            {"past_days": min((date.today() - start).days + 1, 92), "forecast_days": 1},
        )
        recent = daily_from_hourly(payload)
        for day, vals in recent.items():
            if start <= day <= end:
                result[day] = vals
    return result


def upsert_weather(conn, rows: dict[date, tuple]) -> int:
    """Idempotently write {day: (poa, ghi, temp)} into daily_weather. Returns rows touched."""
    sql = """
        INSERT INTO daily_weather (day, poa_kwh_m2, ghi_kwh_m2, temp_avg)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            poa_kwh_m2 = VALUES(poa_kwh_m2),
            ghi_kwh_m2 = VALUES(ghi_kwh_m2),
            temp_avg   = VALUES(temp_avg)
    """
    affected = 0
    with conn.cursor() as cur:
        for day, (poa, ghi, temp) in sorted(rows.items()):
            affected += cur.execute(sql, (day, poa, ghi, temp))
    conn.commit()
    return affected


def _connect():
    return pymysql.connect(
        host=os.getenv("SOLARX_DB_HOST", "localhost"),
        port=int(os.getenv("SOLARX_DB_PORT", "3306")),
        user=os.environ["SOLARX_DB_USER"],
        password=os.environ["SOLARX_DB_PASSWORD"],
        database=os.environ["SOLARX_DB"],
        connect_timeout=10,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch Open-Meteo irradiance into daily_weather.")
    parser.add_argument("--full", action="store_true", help=f"backfill from {FIRST_DAY} to today")
    parser.add_argument("--start", type=date.fromisoformat, help="start day (YYYY-MM-DD)")
    parser.add_argument("--end", type=date.fromisoformat, help="end day (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, default=7, help="default mode: refresh last N days")
    args = parser.parse_args(argv)

    today = date.today()
    if args.full:
        start, end = FIRST_DAY, today
    elif args.start:
        start, end = args.start, (args.end or today)
    else:
        start, end = today - timedelta(days=args.days), today

    rows = fetch_range(start, end)
    conn = _connect()
    try:
        affected = upsert_weather(conn, rows)
    finally:
        conn.close()
    print(f"daily_weather updated for {start}..{end}: {len(rows)} days fetched, {affected} touched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
