import type { ReactNode } from "react";
import { useState } from "react";
import {
  Activity,
  LayoutDashboard,
  LogOut,
  Moon,
  Sun,
  SunMedium,
  Zap,
} from "lucide-react";
import { IconButton } from "./ui";

export type ViewId = "overview" | "health" | "energy" | "day";

const VIEWS: { id: ViewId; label: string; sub: string; icon: typeof Activity }[] = [
  { id: "overview", label: "Overview", sub: "Live snapshot of your system", icon: LayoutDashboard },
  { id: "health", label: "Health", sub: "Performance, degradation & inverter health", icon: Activity },
  { id: "energy", label: "Energy", sub: "Self-consumption & grid exchange", icon: Zap },
  { id: "day", label: "Day", sub: "Intraday power curve", icon: SunMedium },
];

function useTheme() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("solarx-theme", next ? "dark" : "light");
    setDark(next);
  };
  return { dark, toggle };
}

export function Layout({
  view,
  onViewChange,
  onLogout,
  children,
}: {
  view: ViewId;
  onViewChange: (v: ViewId) => void;
  onLogout: () => void;
  children: ReactNode;
}) {
  const { dark, toggle } = useTheme();
  const current = VIEWS.find((v) => v.id === view)!;

  return (
    <div className="flex min-h-screen">
      {/* Sidebar (desktop) */}
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border p-4">
        <div className="flex items-center gap-2.5 px-2 py-3 mb-4">
          <div className="grid place-items-center w-9 h-9 rounded-xl bg-primary/15 text-primary">
            <SunMedium size={20} />
          </div>
          <div>
            <div className="font-semibold leading-tight">SolaX</div>
            <div className="text-xs text-muted">3.6 kWp · single string</div>
          </div>
        </div>
        <nav className="flex flex-col gap-1 text-sm">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              onClick={() => onViewChange(v.id)}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                v.id === view
                  ? "bg-primary/12 text-primary font-medium"
                  : "text-muted hover:text-fg hover:bg-border/40"
              }`}
            >
              <v.icon size={17} />
              <span>{v.label}</span>
            </button>
          ))}
        </nav>
        <div className="mt-auto flex items-center gap-1 px-2 pt-4">
          <IconButton onClick={toggle} title="Toggle theme">
            {dark ? <Moon size={17} /> : <Sun size={17} />}
          </IconButton>
          <IconButton onClick={onLogout} title="Log out">
            <LogOut size={17} />
          </IconButton>
        </div>
      </aside>

      {/* Main column */}
      <main className="flex-1 min-w-0 pb-20 md:pb-0">
        <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-4 border-b border-border bg-bg/80 backdrop-blur">
          <div>
            <h1 className="text-lg font-semibold">{current.label}</h1>
            <p className="text-sm text-muted">{current.sub}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-pos/10 text-pos">
              <span className="w-1.5 h-1.5 rounded-full bg-pos" />
              Online
            </span>
            {/* Theme/logout also reachable on mobile where the sidebar is hidden */}
            <span className="md:hidden flex items-center">
              <IconButton onClick={toggle} title="Toggle theme">
                {dark ? <Moon size={17} /> : <Sun size={17} />}
              </IconButton>
              <IconButton onClick={onLogout} title="Log out">
                <LogOut size={17} />
              </IconButton>
            </span>
          </div>
        </header>
        <div className="p-6 max-w-6xl">{children}</div>
      </main>

      {/* Bottom tab bar (mobile) */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 flex border-t border-border bg-bg z-20">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            onClick={() => onViewChange(v.id)}
            className={`flex-1 flex flex-col items-center gap-1 py-2 text-[10px] ${
              v.id === view ? "text-primary" : "text-muted"
            }`}
          >
            <v.icon size={18} />
            {v.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
