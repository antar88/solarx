import { useEffect, useState } from "react";
import { api, UnauthenticatedError } from "./api";
import { Layout, type ViewId } from "./components/Layout";
import { Spinner } from "./components/ui";
import { Day } from "./views/Day";
import { Energy } from "./views/Energy";
import { Health } from "./views/Health";
import { Login } from "./views/Login";
import { Overview } from "./views/Overview";

type AuthState = "checking" | "anonymous" | "authenticated";

export default function App() {
  const [auth, setAuth] = useState<AuthState>("checking");
  const [view, setView] = useState<ViewId>("overview");

  // Probe the session once on boot: the cookie may still be valid.
  useEffect(() => {
    api
      .overview()
      .then(() => setAuth("authenticated"))
      .catch(() => setAuth("anonymous"));
  }, []);

  // Any 401 raised inside a view (expired session) drops back to the login.
  useEffect(() => {
    const onRejection = (e: PromiseRejectionEvent) => {
      if (e.reason instanceof UnauthenticatedError) {
        e.preventDefault();
        setAuth("anonymous");
      }
    };
    window.addEventListener("unhandledrejection", onRejection);
    return () => window.removeEventListener("unhandledrejection", onRejection);
  }, []);

  if (auth === "checking") return <Spinner />;
  if (auth === "anonymous") return <Login onSuccess={() => setAuth("authenticated")} />;

  return (
    <Layout
      view={view}
      onViewChange={setView}
      onLogout={() => api.logout().then(() => setAuth("anonymous"))}
    >
      {view === "overview" && <Overview />}
      {view === "health" && <Health />}
      {view === "energy" && <Energy />}
      {view === "day" && <Day />}
    </Layout>
  );
}
