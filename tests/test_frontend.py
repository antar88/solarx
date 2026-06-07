"""Contract tests for the static frontend: assets exist and match the API surface."""

from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


def test_static_assets_exist():
    for name in ("index.html", "app.js", "style.css", "vendor/chart.umd.min.js"):
        assert (WEB / name).is_file(), f"missing {name}"


def test_app_js_calls_every_api_endpoint():
    js = (WEB / "app.js").read_text()
    for endpoint in ("/api/login", "/api/logout", "/api/summary", "/api/month"):
        assert endpoint in js, f"frontend never calls {endpoint}"


def test_index_loads_local_assets_not_external_cdn():
    html = (WEB / "index.html").read_text()
    assert "/app.js" in html
    assert "/vendor/chart.umd.min.js" in html
    # No external CDN references (vendored locally for security/CSP).
    assert "http://" not in html
    assert "cdn." not in html


def test_chart_vendor_is_chartjs():
    js = (WEB / "vendor" / "chart.umd.min.js").read_text(errors="ignore")
    assert "chart.js" in js.lower()
