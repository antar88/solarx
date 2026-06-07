"""Tests for the summary and month query logic against a real MySQL test database."""

from datetime import date

from api import queries
from jobs.rollup_daily import run_rollup
from tests.conftest import seed_daily, seed_samples


def test_get_month_pairs_this_year_with_last_year(db_conn):
    seed_daily(
        db_conn,
        [
            ("2026-06-01", 10.0),
            ("2026-06-02", 12.0),
            ("2025-06-01", 9.0),
            ("2025-06-03", 7.0),
        ],
    )
    series = queries.get_month(db_conn, 2026, 6)
    assert len(series) == 30  # June has 30 days
    by_day = {d["day"]: d for d in series}
    assert by_day[1]["kwh_this"] == 10.0
    assert by_day[1]["kwh_last_year"] == 9.0
    assert by_day[2]["kwh_this"] == 12.0
    assert by_day[2]["kwh_last_year"] is None  # no 2025-06-02 row
    assert by_day[3]["kwh_this"] is None  # no 2026-06-03 row
    assert by_day[3]["kwh_last_year"] == 7.0
    assert by_day[15]["kwh_this"] is None and by_day[15]["kwh_last_year"] is None


def test_get_summary_today_and_month_to_date(db_conn):
    today = date.today()
    d1 = today.replace(day=1)
    # Two earlier days this month + today's cumulative samples.
    seed_samples(
        db_conn,
        [
            (f"{d1} 12:00:00", 1000, 5.0),
            (f"{d1.replace(day=2) if d1.day == 1 else d1} 12:00:00", 1000, 6.0),
            (f"{today} 08:00:00", 1200, 2.0),
            (f"{today} 16:00:00", 800, 7.5),  # today's peak
        ],
    )
    summary = queries.get_summary(db_conn, today)
    assert summary["today_kwh"] == 7.5
    assert summary["current_power_w"] == 800.0  # latest by uploadTime
    # month-to-date >= today's energy
    assert summary["month_to_date_kwh"] >= 7.5


def test_get_summary_delta_vs_last_year(db_conn):
    today = date(2026, 6, 10)
    seed_samples(
        db_conn,
        [
            ("2026-06-10 16:00:00", 800, 10.0),  # this year MTD = 10
            ("2025-06-05 16:00:00", 800, 8.0),  # last year span MTD = 8
        ],
    )
    summary = queries.get_summary(db_conn, today)
    assert summary["month_to_date_kwh"] == 10.0
    assert summary["month_to_date_last_year_kwh"] == 8.0
    assert summary["delta_pct"] == 25.0  # (10-8)/8 * 100


def test_get_summary_empty_db(db_conn):
    summary = queries.get_summary(db_conn, date.today())
    assert summary["current_power_w"] is None
    assert summary["today_kwh"] == 0.0
    assert summary["month_to_date_kwh"] == 0.0
    assert summary["delta_pct"] is None


def test_rollup_then_month_endpoint_consistent(db_conn):
    # End-to-end: raw samples -> rollup -> month series.
    seed_samples(
        db_conn,
        [
            ("2026-06-01 12:00:00", 1500, 8.5),
            ("2026-06-01 18:00:00", 300, 11.2),
        ],
    )
    run_rollup(db_conn, days=None)
    series = queries.get_month(db_conn, 2026, 6)
    by_day = {d["day"]: d for d in series}
    assert by_day[1]["kwh_this"] == 11.2
