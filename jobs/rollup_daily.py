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
# Uses a derived-table alias (MariaDB) instead of the deprecated VALUES() function.
#
# Daily grid export/import are deltas of the lifetime cumulative counters
# (feedinenergy/consumeenergy), computed with LAG over consecutive days. For an
# incremental run we read one extra leading day of raw data (so the oldest *written*
# day still has a previous-day value to subtract from) but only upsert days strictly
# inside the requested window — see run_rollup.
_UPSERT = """
INSERT INTO daily_yield
    (day, energy_kwh, peak_acpower, peak_powerdc,
     export_kwh, import_kwh, self_consumed_kwh,
     avg_efficiency_pct, uptime_pct, samples)
SELECT s.day, s.energy_kwh, s.peak_acpower, s.peak_powerdc,
       s.export_kwh, s.import_kwh, s.self_consumed_kwh,
       s.avg_efficiency_pct, s.uptime_pct, s.samples
FROM (
    SELECT w.*,
           GREATEST(w.energy_kwh - COALESCE(w.export_kwh, 0), 0) AS self_consumed_kwh
    FROM (
        SELECT d.*,
               d.feedin_max  - LAG(d.feedin_max)  OVER (ORDER BY d.day) AS export_kwh,
               d.consume_max - LAG(d.consume_max) OVER (ORDER BY d.day) AS import_kwh
        FROM (
            SELECT DATE(uploadTime) AS day,
                   MAX(yieldtoday)  AS energy_kwh,
                   MAX(acpower)     AS peak_acpower,
                   MAX(powerdc1)    AS peak_powerdc,
                   MAX(feedinenergy)   AS feedin_max,
                   MAX(consumeenergy)  AS consume_max,
                   ROUND(100.0 * SUM(CASE WHEN powerdc1 > 100 THEN acpower END)
                         / NULLIF(SUM(CASE WHEN powerdc1 > 100 THEN powerdc1 END), 0), 2)
                       AS avg_efficiency_pct,
                   ROUND(100.0 * SUM(inverterStatus = 102 AND acpower > 0)
                         / NULLIF(SUM(acpower > 0), 0), 2)
                       AS uptime_pct,
                   COUNT(*) AS samples
            FROM inverter_data
            {raw_where}
            GROUP BY DATE(uploadTime)
        ) AS d
    ) AS w
) AS s
{day_where}
ON DUPLICATE KEY UPDATE
    energy_kwh         = s.energy_kwh,
    peak_acpower       = s.peak_acpower,
    peak_powerdc       = s.peak_powerdc,
    export_kwh         = s.export_kwh,
    import_kwh         = s.import_kwh,
    self_consumed_kwh  = s.self_consumed_kwh,
    avg_efficiency_pct = s.avg_efficiency_pct,
    uptime_pct         = s.uptime_pct,
    samples            = s.samples
"""


def run_rollup(conn, days: int | None = 35) -> int:
    """Recompute daily_yield. If days is None, rebuild the full history.

    For an incremental run, raw data for the last ``days`` days is read (which yields
    ``days + 1`` day-buckets) so the cumulative grid deltas have a previous-day anchor,
    but only the most recent ``days`` buckets are written. Returns rows touched.
    """
    if days is None:
        sql = _UPSERT.format(raw_where="", day_where="")
        params: tuple = ()
    else:
        sql = _UPSERT.format(
            raw_where="WHERE uploadTime >= (CURRENT_DATE - INTERVAL %s DAY)",
            day_where="WHERE s.day > (CURRENT_DATE - INTERVAL %s DAY)",
        )
        params = (days, days)
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
