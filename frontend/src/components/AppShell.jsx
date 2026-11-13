import React, { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { api } from "../api.js";
import { STATUS } from "../format.js";

export default function AppShell({ children }) {
  const [health, setHealth] = useState(null);
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
          <NavLink to="/app" data-testid="nav-purchases">Purchases</NavLink>
        </nav>
        <div className="nav-right">
          <span className="badge muted" data-testid="env-badge">Airwallex sandbox</span>
          {health && <span className="mono dim small" data-testid="llm-model">{health.model}</span>}
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
