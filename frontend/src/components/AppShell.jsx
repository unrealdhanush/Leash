import React, { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { api } from "../api.js";
import { Show, UserButton } from "@clerk/react";
import { STATUS } from "../format.js";
import { useMe } from "./auth/Protected.jsx";

export default function AppShell({ children, shared }) {
  const [health, setHealth] = useState(null);
  const me = useMe();
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);
  return (
    <div className="app" data-testid="leash-console">
      <header className="nav">
        <Link to="/" className="brand" data-testid="nav-home">
          <span className="mark">L</span>
          <span className="brand-name">Leash</span>
        </Link>
        <nav className="nav-links">
          {!shared && <NavLink to="/app" end data-testid="nav-purchases">Purchases</NavLink>}
          {!shared && me?.role === "admin" && <NavLink to="/app/team" data-testid="nav-team">Team</NavLink>}
        </nav>
        <div className="nav-right">
          {shared && <span className="badge expected" data-testid="read-only-badge">read-only</span>}
          <span className="badge muted" data-testid="env-badge">Airwallex sandbox</span>
          {health && <span className="mono dim small" data-testid="llm-model">{health.model}</span>}
          {!shared && <Show when="signed-in"><span data-testid="user-menu"><UserButton /></span></Show>}
        </div>
      </header>
      {children}
    </div>
  );
}

export function StatusPill({ status, testid }) {
  return (
    <span className={`pill ${status}`} data-testid={testid}>
      <span className="pill-dot" />
      {STATUS[status] || status}
    </span>
  );
}

export function CardBadge({ status }) {
  if (!status) return <span className="badge muted">no card</span>;
  return status === "INACTIVE" ? <span className="badge frozen">FROZEN</span> : <span className="badge expected">{status}</span>;
}
