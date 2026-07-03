import { useEffect, useState } from "react";
import { Area, AreaChart, CartesianGrid, Legend, Tooltip, XAxis, YAxis } from "recharts";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { DayCurve } from "../api";
import { api, fmtW } from "../api";
import { IconButton, Panel, Spinner } from "../components/ui";
import { axisProps, chartColors, ChartBox, tooltipStyle } from "../components/charts";

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

export function Day() {
  const [selected, setSelected] = useState(() => new Date());
  const [curve, setCurve] = useState<DayCurve | null>(null);

  useEffect(() => {
    let cancelled = false;
    setCurve(null);
    api.day(iso(selected)).then((r) => {
      if (!cancelled) setCurve(r);
    });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const c = chartColors();
  const shift = (days: number) => {
    const d = new Date(selected);
    d.setDate(d.getDate() + days);
    setSelected(d);
  };

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <div className="inline-flex items-center gap-1 rounded-xl border border-border bg-card px-2 py-1.5">
          <IconButton onClick={() => shift(-1)} title="Previous day">
            <ChevronLeft size={17} />
          </IconButton>
          <input
            type="date"
            value={iso(selected)}
            onChange={(e) => {
              if (!e.target.value) return;
              const [y, m, d] = e.target.value.split("-").map(Number);
              setSelected(new Date(y, m - 1, d));
            }}
            className="bg-transparent text-sm font-medium outline-none"
          />
          <IconButton onClick={() => shift(1)} title="Next day">
            <ChevronRight size={17} />
          </IconButton>
        </div>
        <span className="text-sm text-muted">
          {curve?.peak_ac_w != null ? `Peak ${fmtW(curve.peak_ac_w)}` : ""}
        </span>
      </div>

      <Panel title="Power curve" hint="DC input from the panels vs AC output through the day">
        {!curve ? (
          <Spinner />
        ) : curve.samples.length === 0 ? (
          <p className="py-16 text-center text-sm text-muted">No data for this day.</p>
        ) : (
          <ChartBox h={380}>
            <AreaChart data={curve.samples}>
              <defs>
                <linearGradient id="dc-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={c.primary} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={c.primary} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="ac-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={c.blue} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={c.blue} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={c.border} strokeOpacity={0.5} vertical={false} />
              <XAxis dataKey="t" {...axisProps(c.muted)} minTickGap={40} />
              <YAxis {...axisProps(c.muted)} unit=" W" width={64} />
              <Tooltip {...tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area
                type="monotone"
                dataKey="dc"
                name="DC input"
                stroke={c.primary}
                strokeWidth={1.5}
                fill="url(#dc-fill)"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="ac"
                name="AC output"
                stroke={c.blue}
                strokeWidth={1.5}
                fill="url(#ac-fill)"
                dot={false}
              />
            </AreaChart>
          </ChartBox>
        )}
      </Panel>
    </>
  );
}
