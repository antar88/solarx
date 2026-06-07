"""Read queries backing the dashboard endpoints.

Functions take an open DB connection so they are easy to unit-test against a
throwaway database. Daily energy is MAX(yieldtoday) per local day; month-to-date and
"today" figures are computed live from inverter_data so they don't depend on the rollup
job having run yet, while the per-day month series is read from the daily_yield rollup.
"""

import calendar
from datetime import date


def _next_day(d: date) -> date:
    return date.fromordinal(d.toordinal() + 1)


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _pct(this: float, last: float) -> float | None:
    return round((this - last) / last * 100, 1) if last > 0 else None


def _scalar(conn, sql: str, params: tuple = ()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    if row is None:
        return None
    # Works for both DictCursor and tuple cursor
    return next(iter(row.values())) if isinstance(row, dict) else row[0]


def _daily_energy_sum(conn, start: date, end_exclusive: date) -> float:
    """Sum of per-day MAX(yieldtoday) for [start, end_exclusive), live from raw data."""
    val = _scalar(
        conn,
        """
        SELECT COALESCE(SUM(d.e), 0) AS total FROM (
            SELECT MAX(yieldtoday) AS e
            FROM inverter_data
            WHERE uploadTime >= %s AND uploadTime < %s
            GROUP BY DATE(uploadTime)
        ) AS d
        """,
        (start, end_exclusive),
    )
    return float(val or 0)


def get_summary(conn, today: date) -> dict:
    """Headline figures: current power, today's energy, month-to-date vs last year."""
    current_power_w = _scalar(
        conn,
        "SELECT acpower FROM inverter_data ORDER BY uploadTime DESC LIMIT 1",
    )

    today_kwh = _scalar(
        conn,
        "SELECT MAX(yieldtoday) FROM inverter_data WHERE DATE(uploadTime) = %s",
        (today,),
    )

    month_start = today.replace(day=1)
    tomorrow = date.fromordinal(today.toordinal() + 1)
    mtd_kwh = _daily_energy_sum(conn, month_start, tomorrow)

    # Same span last year: 1st of month .. same day-of-month (inclusive) one year back.
    ly_month_start = month_start.replace(year=month_start.year - 1)
    last_dom = min(today.day, calendar.monthrange(ly_month_start.year, ly_month_start.month)[1])
    ly_end = date(ly_month_start.year, ly_month_start.month, last_dom)
    ly_tomorrow = date.fromordinal(ly_end.toordinal() + 1)
    mtd_last_year_kwh = _daily_energy_sum(conn, ly_month_start, ly_tomorrow)

    delta_pct = None
    if mtd_last_year_kwh > 0:
        delta_pct = round((mtd_kwh - mtd_last_year_kwh) / mtd_last_year_kwh * 100, 1)

    return {
        "current_power_w": float(current_power_w) if current_power_w is not None else None,
        "today_kwh": float(today_kwh) if today_kwh is not None else 0.0,
        "month_to_date_kwh": round(mtd_kwh, 2),
        "month_to_date_last_year_kwh": round(mtd_last_year_kwh, 2),
        "delta_pct": delta_pct,
    }


def _rollup_by_day(conn, start: date, end: date) -> dict[int, float]:
    """Map day-of-month -> energy_kwh from daily_yield for [start, end] inclusive."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT day, energy_kwh FROM daily_yield WHERE day BETWEEN %s AND %s",
            (start, end),
        )
        rows = cur.fetchall()
    result = {}
    for row in rows:
        d = row["day"] if isinstance(row, dict) else row[0]
        e = row["energy_kwh"] if isinstance(row, dict) else row[1]
        result[d.day] = float(e)
    return result


def get_month(conn, year: int, month: int, today: date | None = None) -> list[dict]:
    """Per-day energy for the given month vs the same calendar day one year earlier.

    Read from the daily_yield rollup. If ``today`` falls in the requested month, that
    day's value is overlaid live from inverter_data so the current day isn't stale
    while waiting for the nightly rollup.
    """
    ndays = calendar.monthrange(year, month)[1]
    this_year = _rollup_by_day(conn, date(year, month, 1), _month_end(year, month))

    if today is not None and today.year == year and today.month == month:
        live_today = _scalar(
            conn,
            "SELECT MAX(yieldtoday) FROM inverter_data WHERE DATE(uploadTime) = %s",
            (today,),
        )
        if live_today is not None:
            this_year[today.day] = float(live_today)

    last_year = _rollup_by_day(conn, date(year - 1, month, 1), _month_end(year - 1, month))

    series = []
    for day in range(1, ndays + 1):
        series.append(
            {
                "day": day,
                "kwh_this": this_year.get(day),
                "kwh_last_year": last_year.get(day),
            }
        )
    return series


def get_month_summary(conn, year: int, month: int, today: date) -> dict:
    """Headline stats for a *selected* month, adapting to whether it is the live month.

    Current month: totals span the 1st .. today vs the same span last year, and live
    current-power / today figures are included. Past months: full-month totals.
    """
    is_current = year == today.year and month == today.month
    month_start = date(year, month, 1)

    if is_current:
        this_end = _next_day(today)
        ly_last_dom = min(today.day, calendar.monthrange(year - 1, month)[1])
        ly_start = date(year - 1, month, 1)
        ly_end = _next_day(date(year - 1, month, ly_last_dom))
    else:
        this_end = _next_day(_month_end(year, month))
        ly_start = date(year - 1, month, 1)
        ly_end = _next_day(_month_end(year - 1, month))

    total = _daily_energy_sum(conn, month_start, this_end)
    total_ly = _daily_energy_sum(conn, ly_start, ly_end)
    best_day = _scalar(
        conn,
        """
        SELECT MAX(d.e) FROM (
            SELECT MAX(yieldtoday) AS e FROM inverter_data
            WHERE uploadTime >= %s AND uploadTime < %s GROUP BY DATE(uploadTime)
        ) AS d
        """,
        (month_start, this_end),
    )

    out = {
        "is_current_month": is_current,
        "total_kwh": round(total, 2),
        "total_last_year_kwh": round(total_ly, 2),
        "delta_pct": _pct(total, total_ly),
        "best_day_kwh": float(best_day) if best_day is not None else None,
        "current_power_w": None,
        "today_kwh": None,
    }
    if is_current:
        snap = get_summary(conn, today)
        out["current_power_w"] = snap["current_power_w"]
        out["today_kwh"] = snap["today_kwh"]
    return out


def get_year_summary(conn, today: date, year: int | None = None) -> dict:
    """Whole-year energy vs the prior year. For the current year, compares year-to-date
    against the same span last year; for a past year, full year vs full prior year."""
    year = year or today.year
    is_current = year == today.year
    year_start = date(year, 1, 1)

    if is_current:
        this_end = _next_day(today)
        ly_last_dom = min(today.day, calendar.monthrange(year - 1, today.month)[1])
        ly_end = _next_day(date(year - 1, today.month, ly_last_dom))
    else:
        this_end = date(year + 1, 1, 1)
        ly_end = date(year, 1, 1)

    total = _daily_energy_sum(conn, year_start, this_end)
    total_ly = _daily_energy_sum(conn, date(year - 1, 1, 1), ly_end)
    return {
        "year": year,
        "is_current_year": is_current,
        "ytd_kwh": round(total, 2),
        "ytd_last_year_kwh": round(total_ly, 2),
        "delta_pct": _pct(total, total_ly),
    }
