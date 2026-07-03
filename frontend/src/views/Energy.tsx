import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EnergyFlow } from "../api";
import { api, fmtKwh, fmtPct } from "../api";
import { Card, Kpi, Panel, Segmented, Spinner } from "../components/ui";
import { axisProps, chartColors, ChartBox, tooltipStyle } from "../components/charts";

type Period = "last_30_days" | "last_365_days";

export function Energy() {
  const [flow, setFlow] = useState<EnergyFlow | null>(null);
  const [period, setPeriod] = useState<Period>("last_365_days");

  useEffect(() => {
    api.energyFlow().then(setFlow);
  }, []);

  if (!flow) return <Spinner />;
  const c = chartColors();
  const f = flow[period];
  const periodLabel = period === "last_30_days" ? "last 30 days" : "last 12 months";

  const donut = [
    { name: "Own solar", value: f.self_consumed_kwh },
    { name: "Grid import", value: f.import_kwh },
  ];
  const monthly = flow.monthly.slice(-12).map((m) => ({ ...m, label: m.month.slice(2) }));

  return (
    <>
      <div className="mb-4">
        <Segmented<Period>
          value={period}
          onChange={setPeriod}
          options={[
            { value: "last_30_days", label: "Last 30 days" },
            { value: "last_365_days", label: "Last 12 months" },
          ]}
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mb-4">
        <Card>
          <div className="font-medium mb-3">Consumption coverage</div>
          <ChartBox h={176}>
            <PieChart>
              <Pie
                data={donut}
                dataKey="value"
                innerRadius="68%"
                outerRadius="100%"
                paddingAngle={2}
                strokeWidth={0}
              >
                <Cell fill={c.pos} />
                <Cell fill={c.muted} opacity={0.5} />
              </Pie>
              <Tooltip {...tooltipStyle} formatter={(v) => fmtKwh(Number(v))} />
            </PieChart>
          </ChartBox>
          <div className="flex justify-center gap-5 mt-3 text-sm">
            <span className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded" style={{ background: c.pos }} />
              Own solar
            </span>
            <span className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded opacity-50" style={{ background: c.muted }} />
              Grid import
            </span>
          </div>
        </Card>

        <div className="lg:col-span-2 grid grid-cols-2 gap-4">
          <Kpi label="Generation" value={fmtKwh(f.generation_kwh)} sub={periodLabel} />
          <Kpi label="Self-consumed" value={fmtKwh(f.self_consumed_kwh)} sub="used on-site" />
          <Kpi label="Exported" value={fmtKwh(f.export_kwh)} sub="to grid" />
          <Kpi label="Imported" value={fmtKwh(f.import_kwh)} sub="from grid" />
          <Kpi label="Self-consumption" value={fmtPct(f.self_consumption_pct, 1)} sub="of generation" />
          <Kpi label="Self-sufficiency" value={fmtPct(f.self_sufficiency_pct, 1)} sub="of consumption" />
        </div>
      </div>

      <Panel
        title="Monthly energy flow"
        hint="Self-consumed + exported = generated; imported comes from the grid"
      >
        <ChartBox>
          <BarChart data={monthly}>
            <CartesianGrid stroke={c.border} strokeOpacity={0.5} vertical={false} />
            <XAxis dataKey="label" {...axisProps(c.muted)} />
            <YAxis {...axisProps(c.muted)} unit=" kWh" width={70} />
            <Tooltip {...tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey="self_consumed_kwh" name="Self-consumed" stackId="g" fill={c.pos} radius={[0, 0, 0, 0]} />
            <Bar dataKey="export_kwh" name="Exported" stackId="g" fill={c.primary} radius={[4, 4, 0, 0]} />
            <Bar dataKey="import_kwh" name="Imported" stackId="i" fill={c.blue} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartBox>
      </Panel>
    </>
  );
}
