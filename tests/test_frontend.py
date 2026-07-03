"""Contract tests for the React frontend: source structure matches the API surface.

The frontend lives in frontend/ (React + Vite + TS); dist/ is a build artifact and not
part of the repo, so these tests pin the *source* contract: the typed API client must
cover every backend endpoint, and each dashboard view must exist and be wired up.
"""

from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
SRC = FRONTEND / "src"


def test_frontend_project_files_exist():
    for name in ("package.json", "vite.config.ts", "index.html", "src/main.tsx", "src/App.tsx"):
        assert (FRONTEND / name).is_file(), f"missing frontend/{name}"


def test_api_client_calls_every_backend_endpoint():
    client = (SRC / "api.ts").read_text()
    for endpoint in (
        "/api/login",
        "/api/logout",
        "/api/overview",
        "/api/month",
        "/api/performance",
        "/api/energy-flow",
        "/api/day",
    ):
        assert endpoint in client, f"api client never calls {endpoint}"


def test_all_views_exist_and_are_routed():
    app = (SRC / "App.tsx").read_text()
    for view in ("Overview", "Health", "Energy", "Day", "Login"):
        assert (SRC / "views" / f"{view}.tsx").is_file(), f"missing view {view}"
        assert f"<{view}" in app, f"App never renders {view}"


def test_session_expiry_drops_to_login():
    # Regression: a 401 mid-session must show the login, not a broken view.
    app = (SRC / "App.tsx").read_text()
    assert "UnauthenticatedError" in app


def test_dev_proxy_targets_local_api():
    cfg = (FRONTEND / "vite.config.ts").read_text()
    assert "/api" in cfg and "8001" in cfg, "vite dev proxy must forward /api to the backend"
