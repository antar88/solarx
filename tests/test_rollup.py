"""Tests for the daily_yield rollup job against a real MySQL test database."""

from jobs.rollup_daily import run_rollup
from tests.conftest import seed_full_samples, seed_samples


def _daily_rows(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT day, energy_kwh, peak_acpower, samples FROM daily_yield ORDER BY day")
        return cur.fetchall()


def test_rollup_computes_daily_energy_as_max_yieldtoday(db_conn):
    # Two days of cumulative yieldtoday; energy = the day's peak.
    seed_samples(
        db_conn,
        [
            ("2025-06-01 08:00:00", 500, 2.0),
            ("2025-06-01 12:00:00", 1500, 8.5),
            ("2025-06-01 18:00:00", 300, 11.2),  # peak for the day
            ("2025-06-02 09:00:00", 900, 3.0),
            ("2025-06-02 17:00:00", 600, 9.9),  # peak for the day
        ],
    )
    run_rollup(db_conn, days=None)
    rows = _daily_rows(db_conn)
    assert len(rows) == 2
    by_day = {str(r["day"]): r for r in rows}
    assert float(by_day["2025-06-01"]["energy_kwh"]) == 11.2
    assert float(by_day["2025-06-01"]["peak_acpower"]) == 1500.0
    assert by_day["2025-06-01"]["samples"] == 3
    assert float(by_day["2025-06-02"]["energy_kwh"]) == 9.9
    assert by_day["2025-06-02"]["samples"] == 2


def test_rollup_is_idempotent(db_conn):
    seed_samples(
        db_conn,
        [
            ("2025-06-01 12:00:00", 1500, 8.5),
            ("2025-06-01 18:00:00", 300, 11.2),
        ],
    )
    run_rollup(db_conn, days=None)
    run_rollup(db_conn, days=None)  # second pass must not duplicate or change values
    rows = _daily_rows(db_conn)
    assert len(rows) == 1
    assert float(rows[0]["energy_kwh"]) == 11.2


def _all_daily(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM daily_yield ORDER BY day")
        return {str(r["day"]): r for r in cur.fetchall()}


def test_rollup_computes_efficiency_uptime_and_grid_deltas(db_conn):
    seed_full_samples(
        db_conn,
        [
            # 2025-06-01: two generating samples + one sub-threshold dawn sample.
            {
                "uploadTime": "2025-06-01 06:00:00",
                "acpower": 40,
                "yieldtoday": 0.2,
                "powerdc1": 50,
                "feedinenergy": 100.0,
                "consumeenergy": 50.0,
                "inverterStatus": 100,
            },  # dawn: excluded from efficiency, not Normal
            {
                "uploadTime": "2025-06-01 10:00:00",
                "acpower": 900,
                "yieldtoday": 3.0,
                "powerdc1": 1000,
                "feedinenergy": 100.0,
                "consumeenergy": 50.0,
                "inverterStatus": 102,
            },
            {
                "uploadTime": "2025-06-01 14:00:00",
                "acpower": 1800,
                "yieldtoday": 9.0,
                "powerdc1": 2000,
                "feedinenergy": 110.0,
                "consumeenergy": 52.0,
                "inverterStatus": 102,
            },
            # 2025-06-02: one sample; grid counters advance from the prior day.
            {
                "uploadTime": "2025-06-02 14:00:00",
                "acpower": 1000,
                "yieldtoday": 20.0,
                "powerdc1": 1100,
                "feedinenergy": 125.0,
                "consumeenergy": 60.0,
                "inverterStatus": 102,
            },
        ],
    )
    run_rollup(db_conn, days=None)
    rows = _all_daily(db_conn)

    d1 = rows["2025-06-01"]
    assert float(d1["avg_efficiency_pct"]) == 90.00  # (900+1800)/(1000+2000), dawn excluded
    assert float(d1["peak_powerdc"]) == 2000.0
    assert float(d1["uptime_pct"]) == 66.67  # 2 of 3 producing samples in Normal status
    assert d1["export_kwh"] is None  # no previous day in a full rebuild
    assert float(d1["self_consumed_kwh"]) == 9.0  # falls back to generation when export unknown

    d2 = rows["2025-06-02"]
    assert float(d2["export_kwh"]) == 15.0  # 125 - 110
    assert float(d2["import_kwh"]) == 8.0  # 60 - 52
    assert float(d2["self_consumed_kwh"]) == 5.0  # 20 generated - 15 exported


def test_rollup_updates_changed_day(db_conn):
    seed_samples(db_conn, [("2025-06-01 12:00:00", 1000, 5.0)])
    run_rollup(db_conn, days=None)
    # A later sample raises the day's peak; rerun must reflect it.
    seed_samples(db_conn, [("2025-06-01 18:00:00", 800, 9.0)])
    run_rollup(db_conn, days=None)
    rows = _daily_rows(db_conn)
    assert len(rows) == 1
    assert float(rows[0]["energy_kwh"]) == 9.0
    assert rows[0]["samples"] == 2
