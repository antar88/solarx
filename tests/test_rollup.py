"""Tests for the daily_yield rollup job against a real MySQL test database."""

from jobs.rollup_daily import run_rollup
from tests.conftest import seed_samples


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
