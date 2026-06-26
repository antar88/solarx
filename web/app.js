"use strict";

// ===========================================================================
// View toggling: login vs dashboard
// ===========================================================================
const loginView = document.getElementById("login-view");
const dashView = document.getElementById("dash-view");

function showLogin() {
  loginView.classList.remove("hidden");
  dashView.classList.add("hidden");
}
function showDash() {
  loginView.classList.add("hidden");
  dashView.classList.remove("hidden");
}

// ===========================================================================
// API helper
// ===========================================================================
async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "include", ...options });
  if (res.status === 401) {
    showLogin();
    throw new Error("unauthenticated");
  }
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  return res.json();
}

// ===========================================================================
// Login / logout
// ===========================================================================
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const err = document.getElementById("login-error");
  err.classList.add("hidden");
  const res = await fetch("/api/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      username: document.getElementById("username").value,
      password: document.getElementById("password").value,
    }),
  });
  if (res.ok) {
    showDash();
    boot();
  } else {
    err.textContent = res.status === 429 ? "Too many attempts, wait a bit" : "Invalid credentials";
    err.classList.remove("hidden");
  }
});

document.getElementById("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", credentials: "include" });
  showLogin();
});

// ===========================================================================
// Formatting helpers
// ===========================================================================
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const fmtPower = (w) => (w == null ? "–" : w >= 1000 ? (w / 1000).toFixed(2) + " kW" : Math.round(w) + " W");
const fmtKwh = (v, d = 1) => (v == null ? "–" : v.toFixed(d) + " kWh");
const fmtPct = (v, d = 0) => (v == null ? "–" : v.toFixed(d) + "%");
const fmtEnergy = (kwh) => (kwh == null ? "–" : kwh >= 1000 ? (kwh / 1000).toFixed(2) + " MWh" : kwh.toFixed(0) + " kWh");

function deltaSpan(pct) {
  if (pct == null) return "";
  const cls = pct < 0 ? "neg" : "pos";
  const sign = pct > 0 ? "+" : "";
  return `<span class="delta ${cls}">${sign}${pct}%</span>`;
}

function kpi(label, value, sub = "") {
  return `<div class="kpi">
    <span class="k-label">${label}</span>
    <span class="k-value">${value}</span>
    ${sub ? `<span class="k-sub">${sub}</span>` : ""}
  </div>`;
}

// ===========================================================================
// Theme + Chart.js theming
// ===========================================================================
function cssVar(name) {
  return getComputedStyle(document.body).getPropertyValue(name).trim();
}

function applyChartTheme() {
  if (!window.Chart) return;
  Chart.defaults.color = cssVar("--muted");
  Chart.defaults.borderColor = cssVar("--border");
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
}

const themeBtn = document.getElementById("theme-toggle");
function setTheme(light, rerender = true) {
  document.body.classList.toggle("light", light);
  themeBtn.textContent = light ? "☀️" : "🌙";
  localStorage.setItem("solarx-theme", light ? "light" : "dark");
  applyChartTheme();
  if (rerender) renderActiveView(); // redraw charts with the new palette
}
themeBtn.addEventListener("click", () => setTheme(!document.body.classList.contains("light")));

// ===========================================================================
// Chart registry (destroy before redraw to reuse canvases)
// ===========================================================================
const charts = {};
function draw(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

// ===========================================================================
// Tab router
// ===========================================================================
const cache = {}; // view -> last fetched payload
let activeView = "overview";

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (btn) setView(btn.dataset.view);
});

function setView(name) {
  activeView = name;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === name));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.dataset.view === name));
  loadView(name);
}

function loadView(name) {
  if (name === "overview") return loadOverview();
  if (name === "health") return loadHealth();
  if (name === "energy") return loadEnergy();
  if (name === "day") return loadDay();
}

function renderActiveView() {
  // Re-render from cache (used after a theme switch). Falls back to a fresh load.
  if (activeView === "overview" && cache.overview) { renderKpis(cache.overview); renderMonth(cache.month); }
  else if (activeView === "health" && cache.performance) renderHealth(cache.performance);
  else if (activeView === "energy" && cache.energy) renderEnergy(cache.energy);
  else if (activeView === "day" && cache.day) renderDay(cache.day);
  else loadView(activeView);
}

// ===========================================================================
// Overview: KPI grid + month-vs-last-year explorer
// ===========================================================================
let selectedMonth = (() => { const d = new Date(); d.setDate(1); return d; })();
let chartType = "bar";

async function loadOverview() {
  cache.overview = await api("/api/overview");
  renderKpis(cache.overview);
  await loadMonth();
}

function renderKpis(o) {
  document.getElementById("kpi-grid").innerHTML =
    kpi("⚡ Current power", fmtPower(o.current_power_w)) +
    kpi("🔆 Today", fmtKwh(o.today_kwh)) +
    kpi("📅 This month", fmtKwh(o.month_to_date_kwh), `${deltaSpan(o.month_delta_pct)} vs last year`) +
    kpi("🗓️ This year", fmtEnergy(o.ytd_kwh), `${deltaSpan(o.year_delta_pct)} vs last year`) +
    kpi("📈 Perf. ratio (30d)", o.pr_30d == null ? "–" : Math.round(o.pr_30d * 100) + "%") +
    kpi("⚙️ Inverter eff. (30d)", fmtPct(o.efficiency_30d, 1)) +
    kpi("🔋 Self-sufficiency", fmtPct(o.self_sufficiency_year_pct), "last 12 months") +
    kpi("∑ Lifetime", fmtEnergy(o.lifetime_kwh));
}

function pickerValue(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

async function loadMonth() {
  const year = selectedMonth.getFullYear();
  const month = selectedMonth.getMonth() + 1;
  document.getElementById("month-picker").value = pickerValue(selectedMonth);
  cache.month = await api(`/api/month?year=${year}&month=${month}`);
  renderMonth(cache.month);
}

function renderMonth(data) {
  if (!data) return;
  const accent = cssVar("--accent");
  const muted = cssVar("--muted");
  draw("month-chart", {
    type: chartType,
    data: {
      labels: data.days.map((d) => d.day),
      datasets: [
        { label: `${data.year}`, data: data.days.map((d) => d.kwh_this),
          backgroundColor: accent, borderColor: accent, tension: 0.3, borderRadius: 4 },
        { label: `${data.year - 1}`, data: data.days.map((d) => d.kwh_last_year),
          backgroundColor: muted, borderColor: muted, tension: 0.3, borderRadius: 4 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: { y: { title: { display: true, text: "kWh" }, beginAtZero: true } },
      plugins: { legend: { position: "top" } },
    },
  });
}

document.getElementById("prev-month").addEventListener("click", () => {
  selectedMonth.setMonth(selectedMonth.getMonth() - 1); loadMonth();
});
document.getElementById("next-month").addEventListener("click", () => {
  selectedMonth.setMonth(selectedMonth.getMonth() + 1); loadMonth();
});
document.getElementById("month-picker").addEventListener("change", (e) => {
  if (!e.target.value) return;
  const [y, m] = e.target.value.split("-").map(Number);
  selectedMonth = new Date(y, m - 1, 1); loadMonth();
});
document.getElementById("chart-toggle").addEventListener("click", (e) => {
  const btn = e.target.closest("button"); if (!btn) return;
  chartType = btn.dataset.type;
  document.querySelectorAll("#chart-toggle button").forEach((b) => b.classList.toggle("active", b === btn));
  renderMonth(cache.month);
});

// ===========================================================================
// Health & performance
// ===========================================================================
async function loadHealth() {
  cache.performance = await api("/api/performance");
  renderHealth(cache.performance);
}

function renderHealth(perf) {
  const deg = perf.degradation;
  const hero = document.getElementById("degradation-hero");
  if (deg.pct_per_year == null) {
    hero.innerHTML = `<div class="hero-label">Performance trend</div>
      <div class="hero-value">–</div>
      <div class="hero-note">Not enough matched clear-sky months yet to estimate a yearly trend.</div>`;
  } else {
    const v = deg.pct_per_year;
    const cls = v <= -1 ? "neg" : v >= 1 ? "pos" : "";
    const verb = v < 0 ? "loss" : "gain";
    const note = v <= -1.5
      ? "Faster than typical panel ageing (~0.5–1%/yr) — likely soiling. Cleaning may recover part of it."
      : "In line with normal panel ageing.";
    hero.innerHTML = `<div class="hero-label">Year-over-year performance ${verb} (clear days)</div>
      <div class="hero-value delta ${cls}">${v > 0 ? "+" : ""}${v}%<small style="font-size:1rem"> /yr</small></div>
      <div class="hero-note">${note} Based on ${deg.months_compared} matched calendar month(s).</div>`;
  }

  const labels = perf.monthly.map((m) => m.month);
  const accent = cssVar("--accent");
  const muted = cssVar("--muted");
  const accent2 = cssVar("--accent-2");

  draw("pr-chart", {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Clear-day PR", data: perf.monthly.map((m) => m.pr_clear),
          borderColor: accent, backgroundColor: accent, spanGaps: true, tension: 0.3, pointRadius: 2 },
        { label: "All-day PR", data: perf.monthly.map((m) => m.pr),
          borderColor: muted, backgroundColor: muted, borderDash: [4, 4], tension: 0.3, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: { y: { title: { display: true, text: "Performance Ratio" }, suggestedMin: 0.4, suggestedMax: 1 } },
      plugins: { legend: { position: "top" } },
    },
  });

  draw("health-chart", {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Inverter efficiency (%)", data: perf.monthly.map((m) => m.efficiency_pct),
          borderColor: accent2, backgroundColor: accent2, yAxisID: "yEff", tension: 0.3, pointRadius: 0 },
        { label: "Peak DC power (W)", data: perf.monthly.map((m) => m.peak_powerdc),
          borderColor: accent, backgroundColor: accent, yAxisID: "yPk", tension: 0.3, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        yEff: { position: "left", title: { display: true, text: "Efficiency %" }, suggestedMin: 90, suggestedMax: 100 },
        yPk: { position: "right", title: { display: true, text: "Peak DC W" }, grid: { drawOnChartArea: false } },
      },
      plugins: { legend: { position: "top" } },
    },
  });
}

// ===========================================================================
// Energy & self-consumption
// ===========================================================================
let flowPeriod = "last_30_days";

async function loadEnergy() {
  cache.energy = await api("/api/energy-flow");
  renderEnergy(cache.energy);
}

document.getElementById("flow-period").addEventListener("click", (e) => {
  const btn = e.target.closest("button"); if (!btn) return;
  flowPeriod = btn.dataset.period;
  document.querySelectorAll("#flow-period button").forEach((b) => b.classList.toggle("active", b === btn));
  renderEnergy(cache.energy);
});

function renderEnergy(data) {
  const f = data[flowPeriod];
  const accent = cssVar("--accent");
  const accent2 = cssVar("--accent-2");
  const muted = cssVar("--muted");
  const pos = cssVar("--pos");

  // KPI cards
  document.getElementById("flow-kpis").innerHTML =
    kpi("☀️ Generation", fmtEnergy(f.generation_kwh)) +
    kpi("🏠 Self-consumed", fmtEnergy(f.self_consumed_kwh)) +
    kpi("⬆️ Exported", fmtEnergy(f.export_kwh)) +
    kpi("⬇️ Imported", fmtEnergy(f.import_kwh)) +
    kpi("🔆 Self-consumption", fmtPct(f.self_consumption_pct, 1), "of generation used on-site") +
    kpi("🔋 Self-sufficiency", fmtPct(f.self_sufficiency_pct, 1), "of consumption from solar");

  // Donut: consumption covered by own solar vs grid import
  draw("flow-donut", {
    type: "doughnut",
    data: {
      labels: ["Own solar", "Grid import"],
      datasets: [{ data: [f.self_consumed_kwh, f.import_kwh], backgroundColor: [pos, muted], borderWidth: 0 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: "62%",
      plugins: { legend: { display: false } },
    },
  });
  document.getElementById("flow-legend").innerHTML = `
    <div class="row"><span class="dot" style="background:${pos}"></span>Own solar (self-consumed)
      <span class="amt">${fmtEnergy(f.self_consumed_kwh)}</span></div>
    <div class="row"><span class="dot" style="background:${muted}"></span>Grid import
      <span class="amt">${fmtEnergy(f.import_kwh)}</span></div>`;

  // Monthly grouped bars
  const labels = data.monthly.map((m) => m.month);
  draw("flow-chart", {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Self-consumed", data: data.monthly.map((m) => m.self_consumed_kwh),
          backgroundColor: pos, stack: "gen", borderRadius: 3 },
        { label: "Exported", data: data.monthly.map((m) => m.export_kwh),
          backgroundColor: accent, stack: "gen", borderRadius: 3 },
        { label: "Imported", data: data.monthly.map((m) => m.import_kwh),
          backgroundColor: accent2, stack: "grid", borderRadius: 3 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: "kWh" }, beginAtZero: true } },
      plugins: { legend: { position: "top" } },
    },
  });
}

// ===========================================================================
// Day detail (intraday power curve)
// ===========================================================================
let selectedDay = new Date();

function dayValue(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function loadDay() {
  document.getElementById("day-picker").value = dayValue(selectedDay);
  cache.day = await api(`/api/day?date=${dayValue(selectedDay)}`);
  renderDay(cache.day);
}

function renderDay(data) {
  document.getElementById("day-title").textContent = "Power curve · " + data.date;
  document.getElementById("day-peak").textContent =
    data.peak_ac_w != null ? "Peak " + fmtPower(data.peak_ac_w) : "No data";
  const accent = cssVar("--accent");
  const accent2 = cssVar("--accent-2");
  const muted = cssVar("--muted");

  draw("day-chart", {
    type: "line",
    data: {
      labels: data.samples.map((s) => s.t),
      datasets: [
        { label: "DC input (W)", data: data.samples.map((s) => s.dc),
          borderColor: accent, backgroundColor: accent + "33", fill: true, tension: 0.3, pointRadius: 0, borderWidth: 1.5 },
        { label: "AC output (W)", data: data.samples.map((s) => s.ac),
          borderColor: accent2, backgroundColor: accent2 + "22", fill: true, tension: 0.3, pointRadius: 0, borderWidth: 1.5 },
        { label: "Efficiency (%)", data: data.samples.map((s) => s.eff),
          borderColor: muted, yAxisID: "yEff", tension: 0.3, pointRadius: 0, borderWidth: 1, spanGaps: true },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        y: { title: { display: true, text: "Power (W)" }, beginAtZero: true },
        yEff: { position: "right", title: { display: true, text: "Eff %" }, suggestedMin: 80, suggestedMax: 100,
                grid: { drawOnChartArea: false } },
        x: { ticks: { maxTicksLimit: 12 } },
      },
      plugins: { legend: { position: "top" } },
    },
  });
}

document.getElementById("prev-day").addEventListener("click", () => {
  selectedDay.setDate(selectedDay.getDate() - 1); loadDay();
});
document.getElementById("next-day").addEventListener("click", () => {
  selectedDay.setDate(selectedDay.getDate() + 1); loadDay();
});
document.getElementById("day-picker").addEventListener("change", (e) => {
  if (!e.target.value) return;
  const [y, m, d] = e.target.value.split("-").map(Number);
  selectedDay = new Date(y, m - 1, d); loadDay();
});

// ===========================================================================
// Boot
// ===========================================================================
async function boot() {
  setTheme(localStorage.getItem("solarx-theme") === "light", false);
  await loadOverview(); // also reveals 401 -> login if no session
  showDash();
}

boot().catch(() => showLogin());
