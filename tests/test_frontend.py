"""Contract tests for the static frontend: assets exist and match the API surface."""

from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"


def test_static_assets_exist():
    for name in ("index.html", "app.js", "style.css", "vendor/chart.umd.min.js"):
        assert (WEB / name).is_file(), f"missing {name}"


def test_app_js_calls_every_api_endpoint():
    js = (WEB / "app.js").read_text()
    for endpoint in ("/api/login", "/api/logout", "/api/month", "/api/year"):
        assert endpoint in js, f"frontend never calls {endpoint}"


def test_index_has_chart_type_toggle_and_month_picker():
    html = (WEB / "index.html").read_text()
    assert 'type="month"' in html, "month/year picker missing"
    assert 'data-type="line"' in html and 'data-type="bar"' in html, "chart-type toggle missing"


def test_index_has_year_banner():
    html = (WEB / "index.html").read_text()
    assert 'id="year-banner"' in html


def _function_body(js: str, signature: str) -> str:
    """Return the brace-matched body of a function given its signature prefix."""
    start = js.index(signature)
    open_brace = js.index("{", start)
    depth = 0
    for i in range(open_brace, len(js)):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return js[open_brace : i + 1]
    raise AssertionError(f"unbalanced braces after {signature!r}")


def test_boot_reveals_dashboard_on_valid_session():
    # Regression: both views start hidden; the valid-session path must call showDash(),
    # otherwise a logged-in revisit renders the dashboard invisibly (blank page).
    js = (WEB / "app.js").read_text()
    body = _function_body(js, "async function boot")
    assert "showDash()" in body, "boot() must reveal the dashboard when the session is valid"


def test_views_start_hidden_and_have_toggles():
    # The hidden-by-default contract relies on showLogin()/showDash() existing.
    js = (WEB / "app.js").read_text()
    assert "function showLogin()" in js and "function showDash()" in js


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
