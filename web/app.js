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

// API helpers ---------------------------------------------------------------
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
  const body = {
    username: document.getElementById("username").value,
    password: document.getElementById("password").value,
  };
  const res = await fetch("/api/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) {
    showDash();
    load();
  } else {
    err.textContent = res.status === 429 ? "Too many attempts, wait a bit" : "Invalid credentials";
    err.classList.remove("hidden");
  }
});

document.getElementById("logout").addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", credentials: "include" });
  showLogin();
});

// Dashboard state -----------------------------------------------------------
let current = new Date();
let chart = null;
const MONTHS = ["January","February","March","April","May","June",
  "July","August","September","October","November","December"];

function fmtPower(w) {
  if (w == null) return "–";
  return w >= 1000 ? (w / 1000).toFixed(2) + " kW" : Math.round(w) + " W";
}
function fmtKwh(v) {
  return v == null ? "–" : v.toFixed(1) + " kWh";
}

async function loadSummary() {
  const s = await api("/api/summary");
  document.getElementById("s-power").textContent = fmtPower(s.current_power_w);
  document.getElementById("s-today").textContent = fmtKwh(s.today_kwh);
  document.getElementById("s-mtd").textContent = fmtKwh(s.month_to_date_kwh);
  const delta = document.getElementById("s-delta");
  if (s.delta_pct == null) {
    delta.textContent = "–";
    delta.className = "value";
  } else {
    delta.textContent = (s.delta_pct > 0 ? "+" : "") + s.delta_pct + "%";
    delta.className = "value " + (s.delta_pct < 0 ? "neg" : "pos");
  }
}

async function loadMonth() {
  const year = current.getFullYear();
  const month = current.getMonth() + 1;
  document.getElementById("month-label").textContent = `${MONTHS[month - 1]} ${year}`;
  const data = await api(`/api/month?year=${year}&month=${month}`);
  const labels = data.days.map((d) => d.day);
  const thisYear = data.days.map((d) => d.kwh_this);
  const lastYear = data.days.map((d) => d.kwh_last_year);

  const cfg = {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: `${year}`, data: thisYear, backgroundColor: "#f5a623" },
        { label: `${year - 1}`, data: lastYear, backgroundColor: "#b0bec5" },
      ],
    },
    options: {
      responsive: true,
      scales: { y: { title: { display: true, text: "kWh" }, beginAtZero: true } },
      plugins: { legend: { position: "top" } },
    },
  };
  if (chart) {
    chart.data = cfg.data;
    chart.update();
  } else {
    chart = new Chart(document.getElementById("month-chart"), cfg);
  }
}

async function load() {
  await Promise.all([loadSummary(), loadMonth()]);
}

document.getElementById("prev-month").addEventListener("click", () => {
  current.setMonth(current.getMonth() - 1);
  loadMonth();
});
document.getElementById("next-month").addEventListener("click", () => {
  current.setMonth(current.getMonth() + 1);
  loadMonth();
});

// Boot: try to load (cookie may already be valid); fall back to login.
load().catch(() => showLogin());
