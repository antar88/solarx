// Small shadcn-style primitives shared across views.
import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-border bg-card p-5 ${className}`}>{children}</div>
  );
}

export function Kpi({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <Card className="flex flex-col gap-1.5">
      <span className="text-xs font-medium tracking-wide text-muted">{label}</span>
      <span className="text-2xl font-semibold tracking-tight">{value}</span>
      {sub != null && <span className="text-xs text-muted">{sub}</span>}
    </Card>
  );
}

export function DeltaBadge({ value }: { value: number | null }) {
  if (value == null) return null;
  const cls =
    value < 0 ? "text-neg bg-neg/10" : "text-pos bg-pos/10";
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded-md ${cls}`}>
      {value > 0 ? "+" : ""}
      {value}%
    </span>
  );
}

export function Panel({
  title,
  hint,
  children,
  className = "",
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card className={className}>
      <div className="mb-1 font-medium">{title}</div>
      {hint ? <p className="text-xs mb-3 text-muted">{hint}</p> : <div className="mb-3" />}
      {children}
    </Card>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-border overflow-hidden">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`px-3.5 py-1.5 text-sm transition-colors ${
            o.value === value
              ? "bg-primary text-black font-medium"
              : "text-muted hover:text-fg"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function IconButton({
  children,
  onClick,
  title,
}: {
  children: ReactNode;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="grid place-items-center w-8 h-8 rounded-lg text-muted hover:text-fg hover:bg-border/40 transition-colors"
    >
      {children}
    </button>
  );
}

export function Spinner() {
  return (
    <div className="grid place-items-center py-24">
      <div className="w-8 h-8 rounded-full border-2 border-border border-t-primary animate-spin" />
    </div>
  );
}
