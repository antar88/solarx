"""Tests for the Open-Meteo weather job: hourly->daily aggregation and the upsert."""

from datetime import date

from jobs.fetch_weather import daily_from_hourly, upsert_weather


def test_daily_from_hourly_sums_irradiance_and_averages_temp():
    payload = {
        "hourly": {
            "time": ["2025-06-01T10:00", "2025-06-01T11:00", "2025-06-02T10:00"],
            "global_tilted_irradiance": [500, 600, 800],  # W/m²
            "shortwave_radiation": [400, 500, 700],
            "temperature_2m": [20, 22, 25],
        }
    }
    out = daily_from_hourly(payload)
    assert out[date(2025, 6, 1)] == (1.1, 0.9, 21.0)  # (500+600)/1000, (400+500)/1000, avg
    assert out[date(2025, 6, 2)] == (0.8, 0.7, 25.0)


def test_daily_from_hourly_skips_nulls():
    payload = {
        "hourly": {
            "time": ["2025-06-01T10:00", "2025-06-01T11:00"],
            "global_tilted_irradiance": [500, None],
            "shortwave_radiation": [None, None],
            "temperature_2m": [20, None],
        }
    }
    poa, ghi, temp = daily_from_hourly(payload)[date(2025, 6, 1)]
    assert poa == 0.5  # only the 500 sample counted
    assert ghi is None  # all null
    assert temp == 20.0  # only the one reading


def test_upsert_weather_is_idempotent(db_conn):
    rows = {date(2025, 6, 1): (5.2, 4.8, 21.5), date(2025, 6, 2): (6.0, 5.5, 23.0)}
    upsert_weather(db_conn, rows)
    upsert_weather(db_conn, {date(2025, 6, 1): (5.5, 5.0, 22.0)})  # update day 1
    with db_conn.cursor() as cur:
        cur.execute("SELECT day, poa_kwh_m2 FROM daily_weather ORDER BY day")
        result = {str(r["day"]): float(r["poa_kwh_m2"]) for r in cur.fetchall()}
    assert result == {"2025-06-01": 5.5, "2025-06-02": 6.0}
