"""Shared pytest fixtures: a throwaway MySQL schema, seed helpers, and an API client."""

import os
from datetime import datetime
from pathlib import Path

import pymysql
import pymysql.cursors
import pytest

from api import auth
from api.config import Settings

ROOT = Path(__file__).resolve().parents[1]

TEST_PASSWORD = "test-password-123"

# inverter_data DDL matching the production columns the code reads (a subset).
_INVERTER_DDL = """
CREATE TABLE inverter_data (
  inverterSN     varchar(255) NOT NULL,
  sn             varchar(255) NOT NULL,
  acpower        decimal(10,2) DEFAULT '0.00',
  yieldtoday     decimal(10,2) DEFAULT '0.00',
  yieldtotal     decimal(10,2) DEFAULT '0.00',
  powerdc1       decimal(10,2) DEFAULT NULL,
  feedinenergy   decimal(10,2) DEFAULT NULL,
  consumeenergy  decimal(10,2) DEFAULT NULL,
  inverterStatus int           DEFAULT NULL,
  uploadTime     timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  utcDateTime    datetime DEFAULT NULL,
  PRIMARY KEY (inverterSN, sn, uploadTime)
) ENGINE=InnoDB
"""


def _load_env_test() -> dict[str, str]:
    env_file = ROOT / ".env.test"
    values: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip()
    # Environment overrides file (useful in CI).
    for k in ("TEST_DB_HOST", "TEST_DB_PORT", "TEST_DB_USER", "TEST_DB_PASSWORD", "TEST_DB_NAME"):
        if os.getenv(k):
            values[k] = os.environ[k]
    return values


@pytest.fixture(scope="session")
def db_params() -> dict[str, str]:
    v = _load_env_test()
    missing = [k for k in ("TEST_DB_USER", "TEST_DB_PASSWORD", "TEST_DB_NAME") if not v.get(k)]
    if missing:
        pytest.skip(f"Test DB not configured (missing {missing}); see .env.test")
    return v


@pytest.fixture
def db_conn(db_params):
    """Connect to the test DB, rebuild the schema fresh, yield the connection."""
    conn = pymysql.connect(
        host=db_params.get("TEST_DB_HOST", "localhost"),
        port=int(db_params.get("TEST_DB_PORT", 3306)),
        user=db_params["TEST_DB_USER"],
        password=db_params["TEST_DB_PASSWORD"],
        database=db_params["TEST_DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    daily_ddl = (ROOT / "sql" / "01_daily_yield.sql").read_text()
    weather_ddl = (ROOT / "sql" / "04_daily_weather.sql").read_text()
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS inverter_data")
        cur.execute("DROP TABLE IF EXISTS daily_yield")
        cur.execute("DROP TABLE IF EXISTS daily_weather")
        cur.execute(_INVERTER_DDL)
        cur.execute(daily_ddl)
        cur.execute(weather_ddl)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def seed_samples(conn, rows: list[tuple]) -> None:
    """Insert inverter_data rows. Each row: (uploadTime str, acpower, yieldtoday)."""
    sn = "TESTSN0001"
    with conn.cursor() as cur:
        for upload_time, acpower, yieldtoday in rows:
            cur.execute(
                """INSERT INTO inverter_data
                   (inverterSN, sn, acpower, yieldtoday, yieldtotal, uploadTime)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (sn, sn, acpower, yieldtoday, 0, upload_time),
            )
    conn.commit()


def seed_daily(conn, rows: list[tuple]) -> None:
    """Insert daily_yield rows directly. Each row: (day str, energy_kwh)."""
    with conn.cursor() as cur:
        for day, energy in rows:
            cur.execute(
                "INSERT INTO daily_yield (day, energy_kwh, peak_acpower, samples) "
                "VALUES (%s, %s, %s, %s)",
                (day, energy, 0, 1),
            )
    conn.commit()


# Columns a rich sample may set, beyond the always-present identity/time columns.
_RICH_COLS = (
    "acpower",
    "yieldtoday",
    "yieldtotal",
    "powerdc1",
    "feedinenergy",
    "consumeenergy",
    "inverterStatus",
)


def seed_full_samples(conn, rows: list[dict]) -> None:
    """Insert inverter_data rows from dicts. Each dict needs 'uploadTime'; any of
    acpower/yieldtoday/yieldtotal/powerdc1/feedinenergy/consumeenergy/inverterStatus
    may be set (omitted columns stay NULL)."""
    sn = "TESTSN0001"
    with conn.cursor() as cur:
        for row in rows:
            cols = [c for c in _RICH_COLS if c in row]
            placeholders = ", ".join(["%s"] * (3 + len(cols)))
            cur.execute(
                f"INSERT INTO inverter_data (inverterSN, sn, uploadTime, {', '.join(cols)}) "
                f"VALUES ({placeholders})",
                (sn, sn, row["uploadTime"], *(row[c] for c in cols)),
            )
    conn.commit()


_DAILY_COLS = (
    "energy_kwh",
    "peak_acpower",
    "peak_powerdc",
    "export_kwh",
    "import_kwh",
    "self_consumed_kwh",
    "avg_efficiency_pct",
    "uptime_pct",
    "samples",
)


def seed_daily_full(conn, rows: list[dict]) -> None:
    """Insert daily_yield rows from dicts. Each dict needs 'day'; any rollup column may
    be set (energy_kwh/peak_acpower/samples default to 0/0/1 since they are NOT NULL)."""
    defaults = {"energy_kwh": 0, "peak_acpower": 0, "samples": 1}
    with conn.cursor() as cur:
        for row in rows:
            data = {**defaults, **row}
            cols = [c for c in _DAILY_COLS if c in data]
            placeholders = ", ".join(["%s"] * (1 + len(cols)))
            cur.execute(
                f"INSERT INTO daily_yield (day, {', '.join(cols)}) VALUES ({placeholders})",
                (data["day"], *(data[c] for c in cols)),
            )
    conn.commit()


def seed_weather(conn, rows: list[tuple]) -> None:
    """Insert daily_weather rows. Each row: (day str, poa_kwh_m2)."""
    with conn.cursor() as cur:
        for day, poa in rows:
            cur.execute(
                "INSERT INTO daily_weather (day, poa_kwh_m2) VALUES (%s, %s)",
                (day, poa),
            )
    conn.commit()


@pytest.fixture
def test_settings(db_params) -> Settings:
    """Settings pointing the API at the test DB with a known password/secret."""
    return Settings(
        solarx_ro_db_user=db_params["TEST_DB_USER"],
        solarx_ro_db_password=db_params["TEST_DB_PASSWORD"],
        solarx_db=db_params["TEST_DB_NAME"],
        db_host=db_params.get("TEST_DB_HOST", "localhost"),
        db_port=int(db_params.get("TEST_DB_PORT", 3306)),
        dash_username="hantaro88",
        dash_password_hash=auth.hash_password(TEST_PASSWORD),
        jwt_secret="test-secret-not-for-production-0123456789",
        jwt_ttl_hours=12,
        login_max_attempts=5,
        login_window_minutes=15,
    )


@pytest.fixture
def client(db_conn, test_settings):
    """A TestClient with settings/rate-limiter overridden for the test DB.

    base_url is https so Secure cookies are persisted by the client.
    """
    from fastapi.testclient import TestClient

    from api import main

    main.app.dependency_overrides[main.settings_dep] = lambda: test_settings
    main._rate_limiter = auth.LoginRateLimiter(
        test_settings.login_max_attempts, test_settings.login_window_minutes
    )
    with TestClient(main.app, base_url="https://testserver") as c:
        yield c
    main.app.dependency_overrides.clear()


def now_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")
