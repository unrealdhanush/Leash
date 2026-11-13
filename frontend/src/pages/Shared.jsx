import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import AppShell from "../components/AppShell.jsx";
import { PurchaseView } from "./Purchase.jsx";

export default function Shared() {
  const { token } = useParams();
  const [run, setRun] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api.shared(token).then(setRun).catch((e) => setError(e.message));
  }, [token]);

  return (
    <AppShell shared>
      {run
        ? <PurchaseView run={run} events={run.events} readOnly />
        : (
          <div className="page" data-testid="shared-page">
            {error
              ? <div className="empty" data-testid="shared-error"><h2>This link is not active</h2><p>The person who shared it may have turned it off. <Link to="/">About Leash</Link></p></div>
              : <p className="dim">Loading…</p>}
          </div>
        )}
    </AppShell>
  );
}
