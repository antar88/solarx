"""Password verification, JWT issue/verify, and a simple login rate-limiter."""

import time
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()
COOKIE_NAME = "solarx_session"


def hash_password(plaintext: str) -> str:
    """Produce an argon2 hash (used by the one-off setup helper, not at runtime)."""
    return _ph.hash(plaintext)


def verify_password(plaintext: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    try:
        return _ph.verify(stored_hash, plaintext)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def create_token(username: str, secret: str, ttl_hours: int) -> str:
    now = datetime.now(UTC)
    payload = {"sub": username, "iat": now, "exp": now + timedelta(hours=ttl_hours)}
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> str | None:
    """Return the subject (username) if the token is valid, else None."""
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


class LoginRateLimiter:
    """In-memory sliding-window limiter keyed by client identifier (e.g. IP)."""

    def __init__(self, max_attempts: int, window_minutes: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_minutes * 60
        self._hits: dict[str, list[float]] = {}

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self.window_seconds
        self._hits[key] = [t for t in self._hits.get(key, []) if t > cutoff]

    def is_blocked(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        self._prune(key, now)
        return len(self._hits.get(key, [])) >= self.max_attempts

    def record_failure(self, key: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._hits.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
