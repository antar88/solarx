# SolaX Dashboard

Secure web dashboard for solar generation data at **solar.antarmf.com**. Shows the
current month's daily energy day-by-day versus the same month one year ago — to spot
under-performance from dirty or degrading panels.

See [`DESIGN.md`](DESIGN.md) for architecture and [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
for the build plan.

## Layout
```
api/         FastAPI backend (auth + read endpoints)
jobs/        rollup_daily.py — builds the daily_yield rollup from inverter_data
web/         static dashboard (HTML + Chart.js, no build step)
sql/         schema for daily_yield + read-only DB user
deploy/      systemd units, nginx site, setup.sh
tests/       pytest suite (auth, rollup, queries, API, frontend)
check.sh     quality gate: ruff lint + format + pytest — run on every change
```

## Data model
- `inverter_data` (existing): raw 5-minute samples, ingested by `solarx_ingestor.py`.
- `daily_yield` (new): one row per local day. **Daily energy = MAX(yieldtoday)**, bucketed
  by `DATE(uploadTime)` (uploadTime is local time and spans the full history;
  utcDateTime is NULL before 2026-05-16).

## Development
Requires [uv](https://docs.astral.sh/uv/) and a local MySQL.

```bash
uv sync                       # create venv + install deps
./check.sh                    # lint + format-check + run all tests
uv run uvicorn api.main:app --port 8001   # run the API locally
```

Tests use a throwaway MySQL database configured in `.env.test`
(`TEST_DB_HOST/USER/PASSWORD/NAME`). They build the schema fresh each run.

## Rollup
```bash
uv run python -m jobs.rollup_daily            # recompute last 35 days (nightly default)
uv run python -m jobs.rollup_daily --full     # rebuild entire history
```

## Deployment
```bash
sudo DASH_PASSWORD='your-login-password' deploy/setup.sh
```
Generates secrets, creates the read-only DB user, writes `/etc/solarx-api.env`
(mode 640), installs the systemd service + nightly rollup timer, the nginx site, and
issues the TLS certificate. Idempotent.

## Endpoints
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET  | `/api/health` | no | liveness |
| POST | `/api/login`  | no | username+password → HttpOnly JWT cookie |
| POST | `/api/logout` | cookie | clear session |
| GET  | `/api/summary` | cookie | current power, today, month-to-date vs last year |
| GET  | `/api/month?year=&month=` | cookie | per-day kWh this year vs last year |
