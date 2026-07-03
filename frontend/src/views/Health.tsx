import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Performance } from "../api";
import { api } from "../api";
import { Card, Panel, Spinner } from "../components/ui";
import { axisProps, chartColors, ChartBox, tooltipStyle } from "../components/charts";

export function Health() {
  const [perf, setPerf] = useState<Performance | null>(null);

  useEffect(() => {
    api.performance().then(setPerf);
  }, []);

  if (!perf) return <Spinner />;
  const c = chartColors();

  const deg = perf.degradation;
  const v = deg.pct_per_year;
  const monthly = perf.monthly.map((m) => ({ ...m, label: m.month.slice(2) }));
  const latest = [...perf.monthly].reverse();
  const latestPr = latest.find((m) => m.pr_clear != null)?.pr_clear;
  const latestEff = latest.find((m) => m.efficiency_pct != null)?.efficiency_pct;

  const heroColor = v == null ? "" : v <= -1.5 ? "text-primary" : v < 0 ? "" : "text-pos";
  const note =
    v == null
      ? "Not enough matched clear-sky months yet to estimate a yearly trend."
      : v <= -1.5
        ? "Faster than normal panel ageing (~0.5–1%/yr) — most of this is likely soiling, which cleaning can recover."
        : "In line with normal panel ageing.";

  return (
    <>
      <Card className="mb-6 flex flex-col md:flex-row md:items-center gap-6 p-6">
        <div>
          <div className="text-xs font-medium tracking-wide text-muted uppercase">
            Year-over-year performance (clear days)
          </div>
          <div className={`text-5xl font-bold tracking-tight mt-1 ${heroColor}`}>
            {v == null ? "–" : `${v}%`}
            <span className="text-xl font-medium text-muted"> / year</span>
          </div>
        </div>
        <div className="md:border-l md:border-border md:pl-6 flex-1 text-sm text-muted">
          {note}
          {v != null && ` Estimated from ${deg.months_compared} matched clear-sky months.`}
        </div>
        <div className="grid grid-cols-2 gap-6 text-center">
          <div>
            <div className="text-2xl font-semibold">
              {latestPr == null ? "–" : Math.round(latestPr * 100) + "%"}
            </div>
            <div className="text-xs text-muted">PR now</div>
          </div>
          <div>
            <div className="text-2xl font-semibold">
              {latestEff == null ? "–" : latestEff.toFixed(1) + "%"}
            </div>
            <div className="text-xs text-muted">Efficiency</div>
          </div>
        </div>
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel
          title="Performance Ratio"
          hint="Clear-day PR by month — a falling line means degradation or dirt"
        >
          <ChartBox>
            <AreaChart data={monthly}>
              <defs>
                <linearGradient id="pr-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={c.primary} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={c.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={c.border} strokeOpacity={0.5} vertical={false} />
              <XAxis dataKey="label" {...axisProps(c.muted)} />
              <YAxis {...axisProps(c.muted)} domain={[0.4, 0.9]} width={40} />
              <Tooltip {...tooltipStyle} />
              <Area
                type="monotone"
                dataKey="pr_clear"
                name="Clear-day PR"
                stroke={c.primary}
                strokeWidth={2}
                fill="url(#pr-fill)"
                connectNulls
                dot={false}
              />
            </AreaChart>
          </ChartBox>
        </Panel>

        <Panel title="Inverter efficiency" hint="AC/DC conversion — should stay flat">
          <ChartBox>
            <LineChart data={monthly}>
              <CartesianGrid stroke={c.border} strokeOpacity={0.5} vertical={false} />
              <XAxis dataKey="label" {...axisProps(c.muted)} />
              <YAxis {...axisProps(c.muted)} domain={[95, 100]} unit="%" width={48} />
              <Tooltip {...tooltipStyle} />
              <Line
                type="monotone"
                dataKey="efficiency_pct"
                name="Efficiency %"
                stroke={c.blue}
                strokeWidth={2}
                connectNulls
                dot={false}
              />
            </LineChart>
          </ChartBox>
        </Panel>

        <Panel
          title="Peak DC power"
          hint="Monthly maximum from the panels — compare same seasons across years"
          className="lg:col-span-2"
        >
          <ChartBox h={240}>
            <LineChart data={monthly}>
              <CartesianGrid stroke={c.border} strokeOpacity={0.5} vertical={false} />
              <XAxis dataKey="label" {...axisProps(c.muted)} />
              <YAxis {...axisProps(c.muted)} unit=" W" width={64} />
              <Tooltip {...tooltipStyle} />
              <Line
                type="monotone"
                dataKey="peak_powerdc"
                name="Peak DC (W)"
                stroke={c.primary}
                strokeWidth={2}
                connectNulls
                dot={false}
              />
            </LineChart>
          </ChartBox>
        </Panel>
      </div>
    </>
  );
}
