# SolaX Dashboard — System Design

## Goal
A secure web dashboard at `solar.antarmf.com` showing solar generation, starting with:
**current month, day-by-day energy (kWh) vs the same month one year ago** — to spot
under-performance from dirt or panel degradation.

## Data (confirmed)
- DB: MySQL `solarx`, table `inverter_data`, one inverter `XM3302I1281063`.
- Ingestion: `solarx_ingestor.py` via systemd timer every 5 min (since 2026-05-16, v2 API).
- History is **continuous daily from 2024-07-05 to present** → real year-ago baseline exists.
- Key columns:
  - `yieldtoday` — cumulative kWh today (resets midnight). **Daily energy = MAX(yieldtoday) per local day.**
  - `yieldtotal` — lifetime kWh.
  - `acpower` — instantaneous W.
- **Quirks**:
  - `utcDateTime` is NULL before 2026-05-16 (added with v2 API). Use `uploadTime` everywhere.
  - `uploadTime` is **local time** (CEST/CET). Bucket days by `DATE(uploadTime)`.
  - Pre-2026-05 polling is sparse (~25/day) vs ~150/day now; MAX(yieldtoday) is still accurate.

## Architecture
```
Browser (solar.antarmf.com)
   │ HTTPS (certbot TLS)
nginx  ── /        → static dashboard (HTML + Chart.js)
       └─ /api/*   → proxy 127.0.0.1:8001
                       │
                  FastAPI (Python 3.12)  [systemd service]
                   - password login (hashed) → session/JWT
                   - read endpoints
                       │ read-only MySQL user
                  MySQL solarx
                   - inverter_data (existing)
                   - daily_yield (new rollup: 1 row/day)
                       ▲
              daily rollup job (systemd timer)
```

## Components

### 1. Database
- New `daily_yield` rollup table: `day DATE PK, energy_kwh, peak_acpower, samples, updated_at`.
- Daily systemd job recomputes recent days from `inverter_data` (MAX yieldtoday, MAX acpower).
- New **read-only** MySQL user for the API (least privilege; ingestor keeps its write user).

### 2. Backend API — FastAPI
- Runs as `solarx-api.service` on `127.0.0.1:8001` (uvicorn).
- Endpoints (v1):
  - `POST /api/login` — username+password → sets HttpOnly session cookie (JWT).
  - `POST /api/logout`
  - `GET  /api/summary` — today's kWh, current power, month-to-date, vs last year.
  - `GET  /api/month?year=&month=` — array of {day, kwh_this, kwh_last_year}.
- Auth: password hashed with argon2/bcrypt; JWT in HttpOnly+Secure+SameSite cookie.
  Designed to add passkey/WebAuthn later as a second factor/method.

### 3. Frontend — static HTML + Chart.js
- Single page: login form → dashboard.
- Grouped bar chart: this-month vs last-year per day; summary cards on top.
- No build pipeline; served by nginx from a `web/` dir.

### 4. nginx + TLS
- New server block `solar.antarmf.com`, mirrors existing `antarmf.com`.
- certbot cert for the subdomain (needs DNS A/AAAA record → this server).

## Security
- TLS everywhere; HTTP→HTTPS redirect.
- Single user, password hashed at rest; JWT in HttpOnly/Secure/SameSite=Strict cookie.
- API bound to localhost, only reachable through nginx.
- Read-only DB credentials for the API, stored in an env file (mode 600), not in git.
- Rate-limit the login endpoint.

## Deferred (later iterations)
- v2: Open-Meteo irradiance + Performance Ratio (separate dirt vs degradation vs weather).
- Passkey/WebAuthn login.
- More views: lifetime trend, monthly/yearly totals, self-consumption.

## Open prerequisite
- DNS: create `solar.antarmf.com` → this server's IP before certbot can issue the cert.
