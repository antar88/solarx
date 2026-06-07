"""Unit tests for password hashing, JWT, and the login rate-limiter (no DB needed)."""

from api import auth

SECRET = "unit-test-secret-key-0123456789abcd"
OTHER_SECRET = "a-totally-different-secret-key-0123456789"


def test_password_hash_roundtrip():
    h = auth.hash_password("s3cret!")
    assert h != "s3cret!"  # never stored in plaintext
    assert auth.verify_password("s3cret!", h)
    assert not auth.verify_password("wrong", h)


def test_verify_password_empty_hash():
    assert not auth.verify_password("anything", "")


def test_jwt_roundtrip():
    token = auth.create_token("hantaro88", SECRET, 12)
    assert auth.verify_token(token, SECRET) == "hantaro88"


def test_jwt_wrong_secret_rejected():
    token = auth.create_token("hantaro88", SECRET, 12)
    assert auth.verify_token(token, OTHER_SECRET) is None


def test_jwt_expired_rejected():
    token = auth.create_token("hantaro88", SECRET, ttl_hours=-1)  # already expired
    assert auth.verify_token(token, SECRET) is None


def test_rate_limiter_blocks_after_max():
    rl = auth.LoginRateLimiter(max_attempts=3, window_minutes=15)
    key = "1.2.3.4"
    assert not rl.is_blocked(key)
    for _ in range(3):
        rl.record_failure(key)
    assert rl.is_blocked(key)


def test_rate_limiter_window_expires():
    rl = auth.LoginRateLimiter(max_attempts=2, window_minutes=15)
    key = "1.2.3.4"
    t0 = 1000.0
    rl.record_failure(key, now=t0)
    rl.record_failure(key, now=t0)
    assert rl.is_blocked(key, now=t0)
    # 16 minutes later the window has slid past the old hits
    assert not rl.is_blocked(key, now=t0 + 16 * 60)


def test_rate_limiter_reset_on_success():
    rl = auth.LoginRateLimiter(max_attempts=2, window_minutes=15)
    key = "1.2.3.4"
    rl.record_failure(key)
    rl.record_failure(key)
    assert rl.is_blocked(key)
    rl.reset(key)
    assert not rl.is_blocked(key)
