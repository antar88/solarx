# SolaX Dashboard — Implementation Plan

Detailed, step-by-step plan to build the dashboard described in `DESIGN.md`.
Approve this, then we build in the numbered order below. Each step is independently testable.

- **Domain**: `solar.antarmf.com` → `62.238.12.127` (DNS verified ✓)
- **Login username**: `hantaro88`
- **Project root**: `/var/www/antar88.github.io/apis/solarx`

---

## Final file layout
```
apis/solarx/
├── solarx_ingestor.py          # existing — unchanged
├── DESIGN.md                   # existing
├── IMPLEMENTATION.md           # this file
├── api/                        # FastAPI backend
│   ├── main.py                 # app, routes, startup
│   ├── auth.py                 # password verify, JWT issue/verify, login rate-limit
│   ├── db.py                   # read-only MySQL connection pool
│   ├── queries.py              # SQL for summary + month-vs-lastyear
│   ├── config.py               # loads env (settings)
│   └── requirements.txt
├── jobs/
│   └── rollup_daily.py         # recompute daily_yield rollup
├── web/                        # static frontend (served by nginx)
│   ├── index.html
│   ├── app.js
│   └── style.css
├── sql/
│   ├── 01_daily_yield.sql      # rollup table DDL
│   └── 02_readonly_user.sql    # read-only DB user (template; secrets filled at deploy)
└── deploy/
    ├── solarx-api.service      # systemd unit for FastAPI
    ├── solarx-rollup.service   # oneshot rollup
    ├── solarx-rollup.timer     # daily timer
    └── nginx-solar.conf        # nginx server block (pre-certbot)
```
Secrets live in `/etc/solarx-api.env` (mode 600, not in git). `.gitignore` already excludes `__pycache__/`; we add `*.env`.

---

## Step 1 — Database: rollup table, rollup job, read-only user

### 1a. `daily_yield` rollup table (`sql/01_daily_yield.sql`)
```sql
CREATE TABLE IF NOT EXISTS daily_yield (
  day          DATE         NOT NULL PRIMARY KEY,
  energy_kwh   DECIMAL(10,2) NOT NULL,   -- MAX(yieldtoday) for that local day
  peak_acpower DECIMAL(10,2) NOT NULL,   -- MAX(acpower)
  samples      INT          NOT NULL,
  updated_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### 1b. Rollup job (`jobs/rollup_daily.py`)
- Reads `inverter_data`, groups by `DATE(uploadTime)`.
- `energy_kwh = MAX(yieldtoday)`, `peak_acpower = MAX(acpower)`, `samples = COUNT(*)`.
- `INSERT ... ON DUPLICATE KEY UPDATE` so it is idempotent.
- Default run: recompute the **last 35 days** (cheap, keeps today + recent days fresh).
- `--full` flag: rebuild the entire history once (initial backfill, 2024-07 → today).
- Uses the same `/etc/solarx.env` write creds (it writes to `daily_yield`).

**Test**: `python3 jobs/rollup_daily.py --full` then
`SELECT * FROM daily_yield ORDER BY day DESC LIMIT 5;` and spot-check June 2025 vs June 2026.

### 1c. Read-only DB user (`sql/02_readonly_user.sql`)
```sql
CREATE USER IF NOT EXISTS 'solarx_ro'@'localhost' IDENTIFIED BY '<generated>';
GRANT SELECT ON solarx.daily_yield   TO 'solarx_ro'@'localhost';
GRANT SELECT ON solarx.inverter_data TO 'solarx_ro'@'localhost';
FLUSH PRIVILEGES;
```
Password generated at deploy, written to `/etc/solarx-api.env`.

---

## Step 2 — Backend API (FastAPI)

### Config (`/etc/solarx-api.env`, mode 600)
```
SOLARX_RO_DB_USER=solarx_ro
SOLARX_RO_DB_PASSWORD=<generated>
SOLARX_DB=solarx
DASH_USERNAME=hantaro88
DASH_PASSWORD_HASH=<argon2 hash of chosen password>
JWT_SECRET=<generated 32+ bytes>
JWT_TTL_HOURS=12
```
Password hash generated with a one-off `argon2` call at setup — plaintext never stored or committed.

### Dependencies (`api/requirements.txt`)
`fastapi`, `uvicorn[standard]`, `pymysql`, `argon2-cffi`, `pyjwt`, `pydantic-settings`.
Installed into a venv at `apis/solarx/.venv`.

### Endpoints
| Method | Path | Auth | Returns |
|---|---|---|---|
| `POST` | `/api/login` | none | sets HttpOnly JWT cookie; `{ok:true}` / 401 |
| `POST` | `/api/logout` | cookie | clears cookie |
| `GET` | `/api/summary` | cookie | today kWh, current W, month-to-date kWh, same period last year, % delta |
| `GET` | `/api/month?year=&month=` | cookie | `[{day, kwh_this, kwh_last_year}]` (1..31) |
| `GET` | `/api/health` | none | `{ok:true}` (for monitoring) |

### `/api/month` query (core logic)
For the requested month, join this year's daily_yield against the same calendar day one year
earlier:
```sql
SELECT d.day,
       t.energy_kwh  AS kwh_this,
       l.energy_kwh  AS kwh_last_year
FROM (  -- generate day numbers present this month
  SELECT day FROM daily_yield
  WHERE day BETWEEN %s AND %s            -- month start..end this year
) d
LEFT JOIN daily_yield t ON t.day = d.day
LEFT JOIN daily_yield l ON l.day = d.day - INTERVAL 1 YEAR
ORDER BY d.day;
```
(Final version generates a full 1..N day axis so missing days show as gaps, not absent bars.)

### Auth flow
- `POST /api/login {username,password}` → verify username == `DASH_USERNAME`,
  argon2 verify password vs `DASH_PASSWORD_HASH`.
- On success: issue JWT (`sub`, `exp`), set cookie `HttpOnly; Secure; SameSite=Strict; Path=/`.
- Protected routes: dependency reads cookie, verifies JWT, else 401.
- **Login rate-limit**: in-memory counter per IP (e.g. 5 attempts / 15 min) → 429.

**Test**: run `uvicorn api.main:app --port 8001` locally; `curl` login → cookie → `/api/month`.
Verify 401 without cookie, 429 after repeated bad logins.

---

## Step 3 — Frontend (static HTML + Chart.js)

- `index.html`: login form (hidden once authenticated) + dashboard section.
- `app.js`: `fetch` with `credentials:'include'`; on 401 show login; on success load
  `/api/summary` (cards) and `/api/month` (chart). Month selector (prev/next).
- Chart.js grouped bar chart: x = day of month, two series (This year / Last year),
  plus a line/percentage indicator for delta.
- `style.css`: clean responsive layout, mobile-friendly.
- Chart.js loaded from a pinned CDN (or vendored locally to avoid external dependency).

**Test**: open `https://solar.antarmf.com` after step 5; log in; confirm chart renders
June 2026 vs June 2025.

---

## Step 4 — systemd services

### `solarx-api.service`
```ini
[Unit]
Description=SolaX dashboard API (FastAPI)
After=network-online.target mysql.service
Wants=network-online.target

[Service]
EnvironmentFile=/etc/solarx-api.env
WorkingDirectory=/var/www/antar88.github.io/apis/solarx
ExecStart=/var/www/antar88.github.io/apis/solarx/.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8001
Restart=on-failure
DynamicUser=no
User=www-data

[Install]
WantedBy=multi-user.target
```

### `solarx-rollup.service` (oneshot) + `solarx-rollup.timer` (daily, e.g. 00:30 local)
Runs `jobs/rollup_daily.py` to keep yesterday/today fresh. Reuses `/etc/solarx.env`.

**Test**: `systemctl start solarx-api`; `curl 127.0.0.1:8001/api/health`. Trigger rollup timer manually.

---

## Step 5 — nginx + TLS

### `deploy/nginx-solar.conf`
```nginx
server {
    listen 80;
    server_name solar.antarmf.com;
    root /var/www/antar88.github.io/apis/solarx/web;
    index index.html;

    location / { try_files $uri $uri/ /index.html; }

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
Then:
1. Symlink into `sites-enabled`, `nginx -t`, reload.
2. `certbot --nginx -d solar.antarmf.com` → issues cert, rewrites block to 443 + HTTP→HTTPS redirect.
3. Verify `https://solar.antarmf.com` serves the dashboard and `/api/health` works.

---

## Step 6 — Verification (end to end)
- `https://solar.antarmf.com` redirects from HTTP, valid TLS.
- Login with `hantaro88` works; wrong password rejected; rate-limit triggers.
- Dashboard shows current month daily kWh vs one year ago; summary cards correct.
- Cross-check a few days against raw `SELECT MAX(yieldtoday) ... GROUP BY DATE(uploadTime)`.
- API not reachable directly from outside (only via nginx); DB user is read-only.

---

## Security checklist
- [ ] TLS via certbot, HTTP→HTTPS redirect, HSTS header.
- [ ] Password argon2-hashed; plaintext never stored/committed.
- [ ] JWT secret random 32+ bytes; cookie HttpOnly+Secure+SameSite=Strict.
- [ ] API bound to 127.0.0.1 only.
- [ ] DB user `solarx_ro` has SELECT-only on two tables.
- [ ] `/etc/solarx-api.env` mode 600, owner root.
- [ ] Login rate-limited; generic error messages (no user enumeration).
- [ ] `.gitignore` excludes `*.env` and venv.

## Out of scope (future iterations)
- Open-Meteo irradiance + Performance Ratio (dirt vs degradation).
- Passkey/WebAuthn login.
- Lifetime/yearly trend views, self-consumption, battery SoC.
```
