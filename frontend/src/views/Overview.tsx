import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { MonthResponse, Overview as OverviewData } from "../api";
import { api, fmtKwh, fmtPct, fmtW } from "../api";
import { DeltaBadge, IconButton, Kpi, Panel, Spinner } from "../components/ui";
import { axisProps, chartColors, ChartBox, tooltipStyle } from "../components/charts";

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];

function monthKey(d: Date) {
  return { year: d.getFullYear(), month: d.getMonth() + 1 };
}

export function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [selected, setSelected] = useState(() => {
    const d = new Date();
    d.setDate(1);
    return d;
  });
  const [month, setMonth] = useState<MonthResponse | null>(null);

  useEffect(() => {
    api.overview().then(setData);
  }, []);

  useEffect(() => {
    const { year, month: m } = monthKey(selected);
    let cancelled = false;
    api.month(year, m).then((r) => {
      if (!cancelled) setMonth(r);
    });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  if (!data) return <Spinner />;
  const c = chartColors();

  const shift = (delta: number) => {
    const d = new Date(selected);
    d.setMonth(d.getMonth() + delta);
    setSelected(d);
  };

  const chartData =
    month?.days.map((d) => ({
      day: d.day,
      [String(month.year)]: d.kwh_this,
      [String(month.year - 1)]: d.kwh_last_year,
    })) ?? [];

  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Kpi label="Current power" value={fmtW(data.current_power_w)} sub="right now" />
        <Kpi label="Today" value={fmtKwh(data.today_kwh)} sub="so far" />
        <Kpi
          label="This month"
          value={fmtKwh(data.month_to_date_kwh)}
          sub={<><DeltaBadge value={data.month_delta_pct} /> vs last year</>}
        />
        <Kpi
          label="This year"
          value={fmtKwh(data.ytd_kwh)}
          sub={<><DeltaBadge value={data.year_delta_pct} /> vs last year</>}
        />
        <Kpi
          label="Performance ratio"
          value={data.pr_30d == null ? "–" : Math.round(data.pr_30d * 100) + "%"}
          sub="last 30 days"
        />
        <Kpi label="Inverter efficiency" value={fmtPct(data.efficiency_30d, 1)} sub="AC / DC, 30 days" />
        <Kpi label="Self-sufficiency" value={fmtPct(data.self_sufficiency_year_pct, 1)} sub="last 12 months" />
        <Kpi label="Lifetime" value={fmtKwh(data.lifetime_kwh)} sub="total produced" />
      </div>

      <Panel
        title={`Daily energy · ${MONTH_NAMES[selected.getMonth()]} ${selected.getFullYear()}`}
        hint="This year vs same month last year"
      >
        <div className="flex items-center gap-1 mb-3">
          <IconButton onClick={() => shift(-1)} title="Previous month">
            <ChevronLeft size={17} />
          </IconButton>
          <input
            type="month"
            value={`${selected.getFullYear()}-${String(selected.getMonth() + 1).padStart(2, "0")}`}
            onChange={(e) => {
              if (!e.target.value) return;
              const [y, m] = e.target.value.split("-").map(Number);
              setSelected(new Date(y, m - 1, 1));
            }}
            className="rounded-lg border border-border bg-bg px-2.5 py-1 text-sm"
          />
          <IconButton onClick={() => shift(1)} title="Next month">
            <ChevronRight size={17} />
          </IconButton>
          {month && (
            <span className="ml-auto text-sm text-muted">
              {fmtKwh(month.summary.total_kwh)}{" "}
              <DeltaBadge value={month.summary.delta_pct} />
            </span>
          )}
        </div>
        <ChartBox h={300}>
          <BarChart data={chartData}>
            <CartesianGrid stroke={c.border} strokeOpacity={0.5} vertical={false} />
            <XAxis dataKey="day" {...axisProps(c.muted)} />
            <YAxis {...axisProps(c.muted)} unit=" kWh" width={64} />
            <Tooltip {...tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {month && (
              <>
                <Bar dataKey={String(month.year)} fill={c.primary} radius={[4, 4, 0, 0]} maxBarSize={14} />
                <Bar dataKey={String(month.year - 1)} fill={c.muted} fillOpacity={0.45} radius={[4, 4, 0, 0]} maxBarSize={14} />
              </>
            )}
          </BarChart>
        </ChartBox>
      </Panel>
    </>
  );
}
