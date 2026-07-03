# SolaX Dashboard

Secure web dashboard for solar generation data at **solar.antarmf.com**. A tabbed,
dark/light single-page app with four views:

- **Overview** — headline KPIs + current month daily energy vs the same month last year.
- **Health** — **Performance Ratio** (vs Open-Meteo irradiance) and a clear-day
  **degradation rate** (separates dirt/ageing from weather), inverter efficiency, peak DC.
- **Energy** — self-consumption and self-sufficiency (autarky), grid import/export.
- **Day** — the day's 5-minute power curve (AC, DC, instantaneous efficiency).

See [`DESIGN.md`](DESIGN.md) for architecture and [`IMPLEMENTATION.md`](IMPLEMENTATION.md)
for the build plan.

## Layout
```
api/         FastAPI backend (auth + read endpoints + analytics)
jobs/        rollup_daily.py (daily_yield rollup) + fetch_weather.py (Open-Meteo)
frontend/    React + Vite + TypeScript + Tailwind + Recharts SPA
sql/         schema for daily_yield/daily_weather + read-only DB user
deploy/      systemd units, nginx site, setup.sh
tests/       pytest suite (auth, rollup, weather, queries, insights, API, frontend contract)
check.sh     quality gate: ruff lint + format + pytest — run on every change
```

## Data model
- `inverter_data` (existing): raw 5-minute samples, ingested by `solarx_ingestor.py`.
- `daily_yield`: one row per local day. **Daily energy = MAX(yieldtoday)**, bucketed
  by `DATE(uploadTime)` (uploadTime is local time and spans the full history;
  utcDateTime is NULL before 2026-05-16). Also stores `peak_powerdc`, daily grid
  `export_kwh`/`import_kwh` (deltas of the lifetime counters), `self_consumed_kwh`,
  load-weighted `avg_efficiency_pct`, and `uptime_pct`.
- `daily_weather`: one row per day of Open-Meteo plane-of-array insolation
  (`poa_kwh_m2`), used for the Performance Ratio `PR = energy_kwh / (kWp × POA)`.

This system has a **single PV string and no battery**, so per-string and battery
metrics are intentionally absent; grid metering is present and drives the energy view.

## Development
Requires [uv](https://docs.astral.sh/uv/) and a local MySQL.

```bash
uv sync                       # create venv + install deps
./check.sh                    # lint + format-check + run all tests
uv run uvicorn api.main:app --port 8001   # run the API locally
```

### Frontend
Lives in `frontend/` (React + Vite + TS + Tailwind + Recharts). Node isn't installed on
the server, so npm runs through Docker:

```bash
cd frontend
docker run --rm -v "$PWD":/app -w /app node:22-alpine npm install
docker run --rm -v "$PWD":/app -w /app node:22-alpine npm run build   # -> frontend/dist
```
The `solar-web` nginx container serves `frontend/dist` (see the home_server
docker-compose). After changing frontend code: rebuild — nginx picks up the new files
immediately (no restart needed). For local dev with hot reload: `npm run dev` (proxies
`/api` to 127.0.0.1:8001).

Tests use a throwaway MySQL database configured in `.env.test`
(`TEST_DB_HOST/USER/PASSWORD/NAME`). They build the schema fresh each run.

## Rollup & weather jobs
```bash
uv run python -m jobs.rollup_daily            # recompute last 35 days (nightly default)
uv run python -m jobs.rollup_daily --full     # rebuild entire history

uv run python -m jobs.fetch_weather           # refresh last 7 days of irradiance (nightly)
uv run python -m jobs.fetch_weather --full    # backfill irradiance from 2024-07-05 to today
```
The weather job calls Open-Meteo (no API key). System geometry (lat/lon, tilt, azimuth)
defaults to the install in `jobs/fetch_weather.py` and is overridable via `SOLARX_LAT`,
`SOLARX_LON`, `SOLARX_TILT`, `SOLARX_AZIMUTH`. The API's `system_kwp` (default 3.6) feeds
the Performance Ratio.

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
| GET  | `/api/year?year=` | cookie | year-to-date energy vs prior year |
| GET  | `/api/overview` | cookie | headline KPIs (power, today, MTD, YTD, PR, efficiency, autarky, lifetime) |
| GET  | `/api/performance` | cookie | monthly PR/efficiency/peak series + clear-day degradation rate |
| GET  | `/api/energy-flow` | cookie | self-consumption & autarky (last 30d, last 365d, monthly) |
| GET  | `/api/day?date=YYYY-MM-DD` | cookie | the day's 5-minute power curve (AC, DC, efficiency) |
