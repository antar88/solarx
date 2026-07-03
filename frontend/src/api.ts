// Typed client for the FastAPI backend. All requests carry the session cookie;
// a 401 anywhere bubbles up as UnauthenticatedError so the app can show the login.

export class UnauthenticatedError extends Error {
  constructor() {
    super("unauthenticated");
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, { credentials: "include", ...options });
  if (res.status === 401) throw new UnauthenticatedError();
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Response shapes (mirror api/main.py + api/insights.py)
// ---------------------------------------------------------------------------

export interface Overview {
  current_power_w: number | null;
  today_kwh: number;
  month_to_date_kwh: number;
  month_delta_pct: number | null;
  ytd_kwh: number;
  year_delta_pct: number | null;
  pr_30d: number | null;
  efficiency_30d: number | null;
  uptime_30d: number | null;
  self_sufficiency_year_pct: number | null;
  lifetime_kwh: number | null;
}

export interface MonthDay {
  day: number;
  kwh_this: number | null;
  kwh_last_year: number | null;
}

export interface MonthResponse {
  year: number;
  month: number;
  days: MonthDay[];
  summary: {
    is_current_month: boolean;
    total_kwh: number;
    total_last_year_kwh: number;
    delta_pct: number | null;
    best_day_kwh: number | null;
  };
}

export interface MonthlyPerf {
  month: string; // "YYYY-MM"
  energy_kwh: number | null;
  poa_kwh_m2: number | null;
  pr: number | null;
  pr_clear: number | null;
  clear_days: number;
  efficiency_pct: number | null;
  peak_powerdc: number | null;
  export_kwh: number | null;
  import_kwh: number | null;
  self_consumed_kwh: number | null;
  days: number;
}

export interface Performance {
  kwp: number;
  monthly: MonthlyPerf[];
  degradation: { pct_per_year: number | null; months_compared: number };
}

export interface FlowTotals {
  generation_kwh: number;
  export_kwh: number;
  import_kwh: number;
  self_consumed_kwh: number;
  consumption_kwh: number;
  self_consumption_pct: number | null;
  self_sufficiency_pct: number | null;
}

export interface EnergyFlow {
  last_30_days: FlowTotals;
  last_365_days: FlowTotals;
  monthly: {
    month: string;
    generation_kwh: number | null;
    export_kwh: number | null;
    import_kwh: number | null;
    self_consumed_kwh: number | null;
  }[];
}

export interface DayCurve {
  date: string;
  samples: { t: string; ac: number | null; dc: number | null; eff: number | null }[];
  peak_ac_w: number | null;
}

// ---------------------------------------------------------------------------
// Calls
// ---------------------------------------------------------------------------

export const api = {
  login: (username: string, password: string) =>
    fetch("/api/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  logout: () => fetch("/api/logout", { method: "POST", credentials: "include" }),
  overview: () => request<Overview>("/api/overview"),
  month: (year: number, month: number) =>
    request<MonthResponse>(`/api/month?year=${year}&month=${month}`),
  performance: () => request<Performance>("/api/performance"),
  energyFlow: () => request<EnergyFlow>("/api/energy-flow"),
  day: (date: string) => request<DayCurve>(`/api/day?date=${date}`),
};

// ---------------------------------------------------------------------------
// Formatting helpers shared by the views
// ---------------------------------------------------------------------------

export const fmtKwh = (v: number | null | undefined, d = 1): string =>
  v == null ? "–" : v >= 1000 ? (v / 1000).toFixed(2) + " MWh" : v.toFixed(d) + " kWh";

export const fmtW = (w: number | null | undefined): string =>
  w == null ? "–" : w >= 1000 ? (w / 1000).toFixed(2) + " kW" : Math.round(w) + " W";

export const fmtPct = (v: number | null | undefined, d = 0): string =>
  v == null ? "–" : v.toFixed(d) + "%";
