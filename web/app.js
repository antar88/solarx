"use strict";

// View toggling -------------------------------------------------------------
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

// API helper ----------------------------------------------------------------
async function api(path, options = {}) {
  const res = await fetch(path, { credentials: "include", ...options });
  if (res.status === 401) {
    showLogin();
    throw new Error("unauthenticated");
  }
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  return res.json();
}

// Login ---------------------------------------------------------------------
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

// Helpers -------------------------------------------------------------------
const MONTHS = ["January","February","March","April","May","June",
  "July","August","September","October","November","December"];

function fmtPower(w) {
  if (w == null) return "–";
  return w >= 1000 ? (w / 1000).toFixed(2) + " kW" : Math.round(w) + " W";
}
function fmtKwh(v) {
  return v == null ? "–" : v.toFixed(1) + " kWh";
}
function deltaHtml(pct) {
  if (pct == null) return '<span class="value">–</span>';
  const cls = pct < 0 ? "neg" : "pos";
  const sign = pct > 0 ? "+" : "";
  return `<span class="value ${cls}">${sign}${pct}%</span>`;
}
function card(label, valueHtml) {
  return `<div class="stat"><span class="label">${label}</span>${valueHtml}</div>`;
}

// Dashboard state -----------------------------------------------------------
let selected = new Date(); // first day of the selected month
selected.setDate(1);
let chartType = "line";
let chart = null;

function pickerValue(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

// Month cards adapt to current vs past month --------------------------------
function renderCards(summary) {
  const cards = document.getElementById("cards");
  if (summary.is_current_month) {
    cards.innerHTML =
      card("Current power", `<span class="value">${fmtPower(summary.current_power_w)}</span>`) +
      card("Today", `<span class="value">${fmtKwh(summary.today_kwh)}</span>`) +
      card("Month so far", `<span class="value">${fmtKwh(summary.total_kwh)}</span>`) +
      card("vs last year", deltaHtml(summary.delta_pct));
  } else {
    cards.innerHTML =
      card("Month total", `<span class="value">${fmtKwh(summary.total_kwh)}</span>`) +
      card("Last year", `<span class="value">${fmtKwh(summary.total_last_year_kwh)}</span>`) +
      card("vs last year", deltaHtml(summary.delta_pct)) +
      card("Best day", `<span class="value">${fmtKwh(summary.best_day_kwh)}</span>`);
  }
}

function renderChart(data) {
  const year = data.year;
  const labels = data.days.map((d) => d.day);
  const thisYear = data.days.map((d) => d.kwh_this);
  const lastYear = data.days.map((d) => d.kwh_last_year);

  const datasets = [
    {
      label: `${year}`,
      data: thisYear,
      backgroundColor: "#f5a623",
      borderColor: "#f5a623",
      tension: 0.3,
      spanGaps: false,
      pointRadius: 2,
    },
    {
      label: `${year - 1}`,
      data: lastYear,
      backgroundColor: "#b0bec5",
      borderColor: "#b0bec5",
      tension: 0.3,
      spanGaps: false,
      pointRadius: 2,
    },
  ];

  const cfg = {
    type: chartType,
    data: { labels, datasets },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: { y: { title: { display: true, text: "kWh" }, beginAtZero: true } },
      plugins: { legend: { position: "top" } },
    },
  };

  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("month-chart"), cfg);
}

async function loadMonth() {
  const year = selected.getFullYear();
  const month = selected.getMonth() + 1;
  document.getElementById("month-picker").value = pickerValue(selected);
  const data = await api(`/api/month?year=${year}&month=${month}`);
  renderCards(data.summary);
  renderChart(data);
}

async function loadYear() {
  const y = new Date().getFullYear(); // overall comparison always tracks the real year
  const data = await api(`/api/year?year=${y}`);
  document.getElementById("year-title").textContent = `${data.year} vs ${data.year - 1} so far`;
  document.getElementById("year-body").innerHTML =
    `<strong>${fmtKwh(data.ytd_kwh)}</strong> vs ${fmtKwh(data.ytd_last_year_kwh)} ` +
    deltaHtml(data.delta_pct);
}

// Controls ------------------------------------------------------------------
document.getElementById("prev-month").addEventListener("click", () => {
  selected.setMonth(selected.getMonth() - 1);
  loadMonth();
});
document.getElementById("next-month").addEventListener("click", () => {
  selected.setMonth(selected.getMonth() + 1);
  loadMonth();
});
document.getElementById("month-picker").addEventListener("change", (e) => {
  if (!e.target.value) return;
  const [y, m] = e.target.value.split("-").map(Number);
  selected = new Date(y, m - 1, 1);
  loadMonth();
});
document.querySelectorAll(".chart-toggle button").forEach((btn) => {
  btn.addEventListener("click", () => {
    chartType = btn.dataset.type;
    document.querySelectorAll(".chart-toggle button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loadMonth();
  });
});

async function boot() {
  await Promise.all([loadYear(), loadMonth()]);
}

// Try to load (cookie may already be valid); fall back to login.
boot().catch(() => showLogin());
