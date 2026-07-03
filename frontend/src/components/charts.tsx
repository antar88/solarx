// Shared Recharts building blocks: theme-aware colors, tooltip, axes defaults.
import type { ReactNode } from "react";
import { ResponsiveContainer } from "recharts";

// Chart series colors read the same CSS variables as the rest of the UI, so they
// follow the dark/light theme. Recharts needs concrete strings, so we resolve them
// per render via getComputedStyle (cheap; charts re-render on theme change anyway).
export function chartColors() {
  const s = getComputedStyle(document.documentElement);
  const v = (name: string, fallback: string) => s.getPropertyValue(name).trim() || fallback;
  return {
    primary: v("--primary", "hsl(38 95% 55%)"),
    muted: v("--muted", "hsl(240 5% 60%)"),
    border: v("--border", "hsl(240 5% 16%)"),
    pos: v("--pos", "hsl(142 70% 45%)"),
    blue: v("--blue", "hsl(217 91% 60%)"),
  };
}

export const axisProps = (muted: string) =>
  ({
    stroke: muted,
    fontSize: 11,
    tickLine: false,
    axisLine: false,
  }) as const;

export const tooltipStyle = {
  contentStyle: {
    background: "var(--bg)",
    border: "1px solid var(--border)",
    borderRadius: "0.75rem",
    fontSize: 12,
    color: "var(--fg)",
  },
  labelStyle: { color: "var(--muted)" },
} as const;

export function ChartBox({ h = 288, children }: { h?: number; children: ReactNode }) {
  return (
    <div style={{ height: h }}>
      <ResponsiveContainer width="100%" height="100%">
        {children as never}
      </ResponsiveContainer>
    </div>
  );
}
