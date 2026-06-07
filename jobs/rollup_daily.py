"""Recompute the daily_yield rollup from inverter_data.

Daily energy is MAX(yieldtoday) per local calendar day (yieldtoday is a cumulative
counter that resets at midnight). Bucketed by DATE(uploadTime) because uploadTime is
local time and is populated for the full history, while utcDateTime is NULL before the
v2 API switch (2026-05-16).

Usage:
    python -m jobs.rollup_daily            # recompute the last 35 days (default)
    python -m jobs.rollup_daily --full     # rebuild the entire history
    python -m jobs.rollup_daily --days 90  # recompute the last 90 days
"""

import argparse
import os
import sys

import pymysql

# Idempotent upsert: aggregate inverter_data by local day and merge into daily_yield.
# Uses a derived-table alias (MySQL 8.0.19+) instead of the deprecated VALUES().
_UPSERT = """
INSERT INTO daily_yield (day, energy_kwh, peak_acpower, samples)
SELECT src.day, src.energy_kwh, src.peak_acpower, src.samples
FROM (
    SELECT DATE(uploadTime)  AS day,
           MAX(yieldtoday)   AS energy_kwh,
           MAX(acpower)      AS peak_acpower,
           COUNT(*)          AS samples
    FROM inverter_data
    {where}
    GROUP BY DATE(uploadTime)
) AS src
ON DUPLICATE KEY UPDATE
    energy_kwh   = src.energy_kwh,
    peak_acpower = src.peak_acpower,
    samples      = src.samples
"""


def run_rollup(conn, days: int | None = 35) -> int:
    """Recompute daily_yield. If days is None, rebuild the full history.

    Returns the number of rows touched by the upsert.
    """
    if days is None:
        sql = _UPSERT.format(where="")
        params: tuple = ()
    else:
        sql = _UPSERT.format(where="WHERE uploadTime >= (CURRENT_DATE - INTERVAL %s DAY)")
        params = (days,)
    with conn.cursor() as cur:
        affected = cur.execute(sql, params)
    conn.commit()
    return affected


def _connect():
    return pymysql.connect(
        host=os.getenv("SOLARX_DB_HOST", "localhost"),
        user=os.environ["SOLARX_DB_USER"],
        password=os.environ["SOLARX_DB_PASSWORD"],
        database=os.environ["SOLARX_DB"],
        connect_timeout=10,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recompute the daily_yield rollup.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--full", action="store_true", help="rebuild the entire history")
    group.add_argument("--days", type=int, default=35, help="recompute the last N days")
    args = parser.parse_args(argv)

    days = None if args.full else args.days
    conn = _connect()
    try:
        affected = run_rollup(conn, days=days)
    finally:
        conn.close()
    scope = "full history" if days is None else f"last {days} days"
    print(f"daily_yield rollup complete ({scope}): {affected} rows touched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
