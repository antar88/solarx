"""FastAPI application: login + dashboard read endpoints.

The API binds to localhost and is reached only through nginx. Auth is a single user
(username + argon2-hashed password) exchanged for a JWT stored in an HttpOnly cookie.
"""

from datetime import date

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from api import auth, queries
from api.config import Settings, get_settings
from api.db import get_connection

app = FastAPI(title="SolaX Dashboard API", docs_url=None, redoc_url=None)

# Module-level singletons (the rate-limiter must persist across requests).
_settings = get_settings()
_rate_limiter = auth.LoginRateLimiter(_settings.login_max_attempts, _settings.login_window_minutes)


def settings_dep() -> Settings:
    return _settings


class LoginBody(BaseModel):
    username: str
    password: str


def require_user(
    settings: Settings = Depends(settings_dep),
    session: str | None = Cookie(default=None, alias=auth.COOKIE_NAME),
) -> str:
    user = auth.verify_token(session, settings.jwt_secret) if session else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    settings: Settings = Depends(settings_dep),
) -> dict:
    client = request.client.host if request.client else "unknown"
    if _rate_limiter.is_blocked(client):
        raise HTTPException(status_code=429, detail="Too many attempts, try again later")

    ok = body.username == settings.dash_username and auth.verify_password(
        body.password, settings.dash_password_hash
    )
    if not ok:
        _rate_limiter.record_failure(client)
        # Generic message: no user enumeration.
        raise HTTPException(status_code=401, detail="Invalid credentials")

    _rate_limiter.reset(client)
    token = auth.create_token(settings.dash_username, settings.jwt_secret, settings.jwt_ttl_hours)
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_ttl_hours * 3600,
        path="/",
    )
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/summary")
def summary(
    user: str = Depends(require_user),
    settings: Settings = Depends(settings_dep),
) -> dict:
    with get_connection(settings) as conn:
        return queries.get_summary(conn, date.today())


@app.get("/api/month")
def month(
    year: int,
    month: int,
    user: str = Depends(require_user),
    settings: Settings = Depends(settings_dep),
) -> dict:
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="month must be 1..12")
    if not (2000 <= year <= 2100):
        raise HTTPException(status_code=422, detail="year out of range")
    today = date.today()
    with get_connection(settings) as conn:
        return {
            "year": year,
            "month": month,
            "days": queries.get_month(conn, year, month, today=today),
            "summary": queries.get_month_summary(conn, year, month, today),
        }


@app.get("/api/year")
def year(
    year: int,
    user: str = Depends(require_user),
    settings: Settings = Depends(settings_dep),
) -> dict:
    if not (2000 <= year <= 2100):
        raise HTTPException(status_code=422, detail="year out of range")
    with get_connection(settings) as conn:
        return queries.get_year_summary(conn, date.today(), year=year)
