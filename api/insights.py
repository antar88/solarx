"""Analytics queries for the v2 dashboard: Performance Ratio, degradation, inverter
efficiency, energy flows / self-consumption, and the intraday power curve.

These read the daily_yield + daily_weather rollups (and inverter_data for the live
intraday curve). The Performance Ratio is aggregated per month and never shown as a
raw daily value: daily PR is noisy and can exceed 1 on low-irradiance days, whereas
monthly PR is the robust signal for spotting degradation and dirt.
"""

from datetime import date, timedelta

from api import queries

_REF_IRRADIANCE = 1.0  # kW/m²; PR's reference irradiance, so POA in kWh/m² == peak-sun-hours

# A day counts as "clear" when its in-plane insolation is high. The Open-Meteo tilted
# irradiance model is reliable on bright days but underestimates POA on overcast/winter
# days, which would inflate PR — so PR-based degradation is measured on clear days only.
CLEAR_POA_KWH = 5.5
# A month needs at least this many clear days to enter the year-over-year comparison
# (filters out winter months, which barely have any clear days).
MIN_CLEAR_DAYS = 5


def _pr(energy_kwh: float | None, poa_kwh_m2: float | None, kwp: float) -> float | None:
    """Performance Ratio = produced energy / (rated power x in-plane peak-sun-hours)."""
    if not energy_kwh or not poa_kwh_m2 or kwp <= 0:
        return None
    return round(energy_kwh / (kwp * poa_kwh_m2 / _REF_IRRADIANCE), 3)


def monthly_series(conn, kwp: float) -> list[dict]:
    """One row per calendar month over the whole history, with PR and health metrics.

    ``pr`` is the all-days monthly Performance Ratio (handy for the chart but noisy in
    winter); ``pr_clear`` averages the daily PR over clear days only and is the figure
    the degradation rate is built from.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DATE_FORMAT(y.day, '%%Y-%%m')              AS ym,
                   ROUND(SUM(y.energy_kwh), 2)                AS energy_kwh,
                   ROUND(SUM(w.poa_kwh_m2), 3)                AS poa_kwh_m2,
                   ROUND(AVG(y.avg_efficiency_pct), 2)        AS efficiency_pct,
                   ROUND(MAX(y.peak_powerdc), 0)              AS peak_powerdc,
                   ROUND(SUM(y.export_kwh), 2)                AS export_kwh,
                   ROUND(SUM(y.import_kwh), 2)                AS import_kwh,
                   ROUND(SUM(y.self_consumed_kwh), 2)         AS self_consumed_kwh,
                   ROUND(AVG(CASE WHEN w.poa_kwh_m2 >= %s
                                  THEN y.energy_kwh / (%s * w.poa_kwh_m2) END), 3) AS pr_clear,
                   CAST(SUM(w.poa_kwh_m2 >= %s) AS UNSIGNED)  AS clear_days,
                   COUNT(*)                                   AS days
            FROM daily_yield y
            LEFT JOIN daily_weather w ON w.day = y.day
            GROUP BY ym
            ORDER BY ym
            """,
            (CLEAR_POA_KWH, kwp, CLEAR_POA_KWH),
        )
        rows = cur.fetchall()

    out = []
    for r in rows:
        energy = float(r["energy_kwh"]) if r["energy_kwh"] is not None else None
        poa = float(r["poa_kwh_m2"]) if r["poa_kwh_m2"] is not None else None
        out.append(
            {
                "month": r["ym"],
                "energy_kwh": energy,
                "poa_kwh_m2": poa,
                "pr": _pr(energy, poa, kwp),
                "pr_clear": float(r["pr_clear"]) if r["pr_clear"] is not None else None,
                "clear_days": int(r["clear_days"]) if r["clear_days"] is not None else 0,
                "efficiency_pct": float(r["efficiency_pct"]) if r["efficiency_pct"] else None,
                "peak_powerdc": float(r["peak_powerdc"]) if r["peak_powerdc"] else None,
                "export_kwh": float(r["export_kwh"]) if r["export_kwh"] is not None else None,
                "import_kwh": float(r["import_kwh"]) if r["import_kwh"] is not None else None,
                "self_consumed_kwh": (
                    float(r["self_consumed_kwh"]) if r["self_consumed_kwh"] is not None else None
                ),
                "days": int(r["days"]),
            }
        )
    return out


def _degradation(series: list[dict], current_ym: str) -> dict:
    """Annual degradation rate from clear-day PR, averaged over calendar months that
    appear in two consecutive years with enough clear days.

    Matching the same calendar month across years cancels PR's strong seasonal swing,
    so the mean of the per-month year-over-year changes is a stable annual rate. A
    negative value means the system is losing performance (degradation and/or soiling).
    The incomplete current month is excluded.
    """
    pr_by_month = {
        m["month"]: m["pr_clear"]
        for m in series
        if m["month"] != current_ym and m["pr_clear"] and m["clear_days"] >= MIN_CLEAR_DAYS
    }
    changes: list[float] = []
    for ym, pr_now in pr_by_month.items():
        year, month = ym.split("-")
        pr_prev = pr_by_month.get(f"{int(year) - 1}-{month}")
        if pr_prev:
            changes.append((pr_now - pr_prev) / pr_prev * 100)
    if not changes:
        return {"pct_per_year": None, "months_compared": 0}
    return {"pct_per_year": round(sum(changes) / len(changes), 2), "months_compared": len(changes)}


def get_performance(conn, today: date, kwp: float) -> dict:
    """Monthly PR / efficiency / peak series plus the derived annual degradation rate."""
    series = monthly_series(conn, kwp)
    current_ym = today.strftime("%Y-%m")
    return {
        "kwp": kwp,
        "monthly": series,
        "degradation": _degradation(series, current_ym),
    }


def _flow_totals(conn, start: date, end_inclusive: date) -> dict:
    """Aggregate energy flows over [start, end] inclusive from the daily rollup."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ROUND(SUM(energy_kwh), 1)        AS generation_kwh,
                   ROUND(SUM(export_kwh), 1)        AS export_kwh,
                   ROUND(SUM(import_kwh), 1)        AS import_kwh,
                   ROUND(SUM(self_consumed_kwh), 1) AS self_consumed_kwh
            FROM daily_yield
            WHERE day BETWEEN %s AND %s
            """,
            (start, end_inclusive),
        )
        r = cur.fetchone()

    gen = float(r["generation_kwh"]) if r and r["generation_kwh"] is not None else 0.0
    exp = float(r["export_kwh"]) if r and r["export_kwh"] is not None else 0.0
    imp = float(r["import_kwh"]) if r and r["import_kwh"] is not None else 0.0
    self_c = float(r["self_consumed_kwh"]) if r and r["self_consumed_kwh"] is not None else 0.0
    load = self_c + imp
    return {
        "generation_kwh": round(gen, 1),
        "export_kwh": round(exp, 1),
        "import_kwh": round(imp, 1),
        "self_consumed_kwh": round(self_c, 1),
        "consumption_kwh": round(load, 1),
        # share of generation used on-site
        "self_consumption_pct": round(self_c / gen * 100, 1) if gen > 0 else None,
        # share of consumption covered by own solar
        "self_sufficiency_pct": round(self_c / load * 100, 1) if load > 0 else None,
    }


def get_energy_flow(conn, today: date, kwp: float) -> dict:
    """Self-consumption / autarky: rolling 30-day and 365-day averages plus a monthly series."""
    series = monthly_series(conn, kwp)
    return {
        "last_30_days": _flow_totals(conn, today - timedelta(days=29), today),
        "last_365_days": _flow_totals(conn, today - timedelta(days=364), today),
        "monthly": [
            {
                "month": m["month"],
                "generation_kwh": m["energy_kwh"],
                "export_kwh": m["export_kwh"],
                "import_kwh": m["import_kwh"],
                "self_consumed_kwh": m["self_consumed_kwh"],
            }
            for m in series
        ],
    }


def get_intraday(conn, day: date) -> dict:
    """The day's 5-minute power curve: AC output, DC input, and instantaneous efficiency."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT uploadTime, acpower, powerdc1
            FROM inverter_data
            WHERE DATE(uploadTime) = %s
            ORDER BY uploadTime
            """,
            (day,),
        )
        rows = cur.fetchall()

    samples = []
    for r in rows:
        ac = float(r["acpower"]) if r["acpower"] is not None else None
        dc = float(r["powerdc1"]) if r["powerdc1"] is not None else None
        eff = round(ac / dc * 100, 1) if ac is not None and dc and dc > 100 else None
        samples.append({"t": r["uploadTime"].strftime("%H:%M"), "ac": ac, "dc": dc, "eff": eff})
    peak = max((s["ac"] for s in samples if s["ac"] is not None), default=None)
    return {"date": day.isoformat(), "samples": samples, "peak_ac_w": peak}


def get_overview(conn, today: date, kwp: float) -> dict:
    """Headline KPIs for the landing view, composed from the existing + new queries."""
    summary = queries.get_summary(conn, today)
    year = queries.get_year_summary(conn, today)

    # Recent PR over the last 30 complete days (exclude today's partial reading).
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ROUND(SUM(y.energy_kwh), 2) AS energy, ROUND(SUM(w.poa_kwh_m2), 3) AS poa,
                   ROUND(AVG(y.avg_efficiency_pct), 2) AS eff, ROUND(AVG(y.uptime_pct), 2) AS up
            FROM daily_yield y
            JOIN daily_weather w ON w.day = y.day
            WHERE y.day BETWEEN %s AND %s
            """,
            (today - timedelta(days=30), today - timedelta(days=1)),
        )
        r = cur.fetchone()
    energy_30 = float(r["energy"]) if r and r["energy"] is not None else None
    poa_30 = float(r["poa"]) if r and r["poa"] is not None else None

    lifetime = queries._scalar(conn, "SELECT MAX(yieldtotal) FROM inverter_data")
    flow_year = _flow_totals(conn, today - timedelta(days=364), today)

    return {
        "current_power_w": summary["current_power_w"],
        "today_kwh": summary["today_kwh"],
        "month_to_date_kwh": summary["month_to_date_kwh"],
        "month_delta_pct": summary["delta_pct"],
        "ytd_kwh": year["ytd_kwh"],
        "year_delta_pct": year["delta_pct"],
        "pr_30d": _pr(energy_30, poa_30, kwp),
        "efficiency_30d": float(r["eff"]) if r and r["eff"] is not None else None,
        "uptime_30d": float(r["up"]) if r and r["up"] is not None else None,
        "self_sufficiency_year_pct": flow_year["self_sufficiency_pct"],
        "lifetime_kwh": round(float(lifetime), 1) if lifetime is not None else None,
    }
