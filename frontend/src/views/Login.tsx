import { useState } from "react";
import { SunMedium } from "lucide-react";
import { api } from "../api";

export function Login({ onSuccess }: { onSuccess: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const form = new FormData(e.currentTarget);
    try {
      const res = await api.login(String(form.get("username")), String(form.get("password")));
      if (res.ok) onSuccess();
      else setError(res.status === 429 ? "Too many attempts, wait a bit" : "Invalid credentials");
    } catch {
      setError("Network error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-4">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-8 text-center">
        <div className="mx-auto grid place-items-center w-12 h-12 rounded-2xl bg-primary/15 text-primary mb-3">
          <SunMedium size={26} />
        </div>
        <h1 className="text-xl font-semibold">SolaX</h1>
        <p className="text-sm text-muted mb-6">Solar generation dashboard</p>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <input
            name="username"
            placeholder="Username"
            autoComplete="username"
            required
            className="rounded-xl border border-border bg-bg px-3.5 py-2.5 text-sm outline-none focus:border-primary"
          />
          <input
            name="password"
            type="password"
            placeholder="Password"
            autoComplete="current-password"
            required
            className="rounded-xl border border-border bg-bg px-3.5 py-2.5 text-sm outline-none focus:border-primary"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-primary text-black font-semibold py-2.5 text-sm hover:brightness-105 disabled:opacity-60 transition"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
          {error && <p className="text-sm text-neg">{error}</p>}
        </form>
      </div>
    </div>
  );
}
