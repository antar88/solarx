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


def test_get_month_overlays_live_today(db_conn):
    # daily_yield has a stale value for today; live inverter_data is higher.
    today = date(2026, 6, 7)
    seed_daily(db_conn, [("2026-06-07", 5.0)])  # stale rollup value
    seed_samples(db_conn, [("2026-06-07 16:00:00", 800, 12.3)])  # live, higher
    series = queries.get_month(db_conn, 2026, 6, today=today)
    by_day = {d["day"]: d for d in series}
    assert by_day[7]["kwh_this"] == 12.3  # live value wins for today


def test_get_month_summary_current_month(db_conn):
    today = date(2026, 6, 10)
    seed_samples(
        db_conn,
        [
            ("2026-06-01 16:00:00", 700, 10.0),
            ("2026-06-10 08:00:00", 1200, 3.0),
            ("2026-06-10 16:00:00", 600, 8.0),  # today's peak
            ("2025-06-01 16:00:00", 700, 9.0),
            ("2025-06-10 16:00:00", 700, 7.0),
        ],
    )
    s = queries.get_month_summary(db_conn, 2026, 6, today)
    assert s["is_current_month"] is True
    assert s["total_kwh"] == 18.0  # 10 + 8 (1st..today)
    assert s["total_last_year_kwh"] == 16.0  # 9 + 7
    assert s["delta_pct"] == 12.5  # (18-16)/16*100
    assert s["today_kwh"] == 8.0
    assert s["current_power_w"] == 600.0
    assert s["best_day_kwh"] == 10.0


def test_get_month_summary_past_month(db_conn):
    today = date(2026, 6, 10)
    # Viewing May 2026 (a past, complete month) vs May 2025.
    seed_samples(
        db_conn,
        [
            ("2026-05-15 16:00:00", 700, 20.0),
            ("2026-05-20 16:00:00", 700, 15.0),
            ("2025-05-15 16:00:00", 700, 18.0),
        ],
    )
    s = queries.get_month_summary(db_conn, 2026, 5, today)
    assert s["is_current_month"] is False
    assert s["total_kwh"] == 35.0
    assert s["total_last_year_kwh"] == 18.0
    assert s["best_day_kwh"] == 20.0
    assert s["current_power_w"] is None
    assert s["today_kwh"] is None


def test_get_year_summary_year_to_date(db_conn):
    today = date(2026, 6, 10)
    seed_samples(
        db_conn,
        [
            ("2026-03-01 16:00:00", 700, 30.0),
            ("2026-06-10 16:00:00", 700, 20.0),  # within YTD span
            ("2025-03-01 16:00:00", 700, 25.0),
            ("2025-06-10 16:00:00", 700, 15.0),  # within same span last year
            ("2025-09-01 16:00:00", 700, 99.0),  # AFTER the span -> excluded
        ],
    )
    s = queries.get_year_summary(db_conn, today, year=2026)
    assert s["is_current_year"] is True
    assert s["ytd_kwh"] == 50.0
    assert s["ytd_last_year_kwh"] == 40.0  # 25 + 15, the Sep row excluded
    assert s["delta_pct"] == 25.0


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
