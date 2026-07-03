"""Tests for the v2 analytics: Performance Ratio, degradation, energy flows, intraday."""

from datetime import date, timedelta

import pytest

from api import insights
from tests.conftest import seed_daily_full, seed_full_samples, seed_weather

KWP = 3.6


def test_pr_formula():
    assert insights._pr(20.0, 7.0, KWP) == round(20.0 / (3.6 * 7.0), 3)  # 0.794
    assert insights._pr(0, 7.0, KWP) is None
    assert insights._pr(20.0, 0, KWP) is None
    assert insights._pr(20.0, 7.0, 0) is None


def test_monthly_series_computes_pr(db_conn):
    seed_daily_full(
        db_conn,
        [
            {"day": "2025-06-01", "energy_kwh": 18.0, "avg_efficiency_pct": 98.0},
            {"day": "2025-06-02", "energy_kwh": 20.0, "avg_efficiency_pct": 98.5},
        ],
    )
    seed_weather(db_conn, [("2025-06-01", 7.0), ("2025-06-02", 7.0)])
    series = insights.monthly_series(db_conn, KWP)
    assert len(series) == 1
    m = series[0]
    assert m["month"] == "2025-06"
    assert m["energy_kwh"] == 38.0
    assert m["poa_kwh_m2"] == 14.0
    assert m["pr"] == round(38.0 / (3.6 * 14.0), 3)  # 0.754
    assert m["efficiency_pct"] == 98.25


def test_degradation_uses_clear_days_year_over_year(db_conn):
    # 6 clear days each June (poa 7.0 >= 5.5 threshold); 2026 generates 10% less.
    daily, weather = [], []
    for d in range(1, 7):
        daily.append({"day": f"2025-06-0{d}", "energy_kwh": 20.0})
        daily.append({"day": f"2026-06-0{d}", "energy_kwh": 18.0})  # 10% less -> lower PR
        weather.append((f"2025-06-0{d}", 7.0))
        weather.append((f"2026-06-0{d}", 7.0))
    seed_daily_full(db_conn, daily)
    seed_weather(db_conn, weather)
    perf = insights.get_performance(db_conn, date(2026, 12, 15), KWP)
    deg = perf["degradation"]
    assert deg["months_compared"] == 1  # only June qualifies (enough clear days both years)
    assert deg["pct_per_year"] == pytest.approx(-10.0, abs=0.2)


def test_degradation_ignores_months_without_enough_clear_days(db_conn):
    # Only 2 clear days per month -> below MIN_CLEAR_DAYS, excluded from the comparison.
    seed_daily_full(
        db_conn,
        [
            {"day": "2025-06-01", "energy_kwh": 20.0},
            {"day": "2025-06-02", "energy_kwh": 20.0},
            {"day": "2026-06-01", "energy_kwh": 18.0},
            {"day": "2026-06-02", "energy_kwh": 18.0},
        ],
    )
    seed_weather(
        db_conn,
        [("2025-06-01", 7.0), ("2025-06-02", 7.0), ("2026-06-01", 7.0), ("2026-06-02", 7.0)],
    )
    deg = insights.get_performance(db_conn, date(2026, 12, 15), KWP)["degradation"]
    assert deg["months_compared"] == 0
    assert deg["pct_per_year"] is None


def test_energy_flow_rates(db_conn):
    today = date.today()
    d = (today - timedelta(days=2)).isoformat()
    seed_daily_full(
        db_conn,
        [
            {
                "day": d,
                "energy_kwh": 10.0,
                "export_kwh": 6.0,
                "import_kwh": 4.0,
                "self_consumed_kwh": 4.0,
            }
        ],
    )
    flow = insights.get_energy_flow(db_conn, today, KWP)
    last30 = flow["last_30_days"]
    assert last30["generation_kwh"] == 10.0
    assert last30["consumption_kwh"] == 8.0  # self 4 + import 4
    assert last30["self_consumption_pct"] == 40.0  # 4/10
    assert last30["self_sufficiency_pct"] == 50.0  # 4/8


def test_intraday_curve_and_efficiency(db_conn):
    seed_full_samples(
        db_conn,
        [
            {"uploadTime": "2025-06-01 12:00:00", "acpower": 1900, "powerdc1": 2000},
            {"uploadTime": "2025-06-01 06:00:00", "acpower": 40, "powerdc1": 50},  # sub-threshold
        ],
    )
    out = insights.get_intraday(db_conn, date(2025, 6, 1))
    assert out["peak_ac_w"] == 1900.0
    by_t = {s["t"]: s for s in out["samples"]}
    assert by_t["12:00"]["eff"] == 95.0  # 1900/2000
    assert by_t["06:00"]["eff"] is None  # DC below 100 W -> efficiency not meaningful


def test_overview_has_headline_keys(db_conn):
    out = insights.get_overview(db_conn, date.today(), KWP)
    for key in (
        "current_power_w",
        "today_kwh",
        "month_to_date_kwh",
        "ytd_kwh",
        "pr_30d",
        "efficiency_30d",
        "self_sufficiency_year_pct",
        "lifetime_kwh",
    ):
        assert key in out
