import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { when } from "../format.js";
import AppShell from "../components/AppShell.jsx";
import { useMe } from "../components/auth/Protected.jsx";

const ROLE_TEXT = { admin: "Admin", member: "Member", pending: "Waiting for approval" };

export default function Team() {
  const me = useMe();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const load = useCallback(() => api.users().then(setData).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
  }, [load]);

  const setRole = async (userId, role) => {
    setError(null);
    try {
      await api.setRole(userId, role);
    } catch (e) {
      setError(e.message);
    }
    load();
  };

  return (
    <AppShell>
      <main className="page" data-testid="team-page">
        <h1>Team</h1>
        <p className="cmp-verdict">People who sign in wait here until an admin lets them in. Members can start, approve and see purchases; admins can also manage this list.</p>
        {error && <div className="banner error" data-testid="app-error">{error}</div>}
        <div className="plist">
          {data?.users.map((u) => (
            <div className={`trow ${u.role === "pending" ? "waiting" : ""}`} key={u.user_id} data-testid={`team-row-${u.user_id}`}>
              <span className="prow-vendor">
                <b>{u.name || u.email || u.user_id}{u.user_id === me.user_id ? " (you)" : ""}</b>
                <small className="mono">{u.email}</small>
              </span>
              <span className="dim small">{u.joined_at ? `joined ${when(u.joined_at)}` : ""}</span>
              {u.role === "pending" && <button className="btn primary small-btn" onClick={() => setRole(u.user_id, "member")} data-testid={`team-approve-${u.user_id}`}>Let in</button>}
              <select value={u.role} onChange={(e) => setRole(u.user_id, e.target.value)} data-testid={`team-role-${u.user_id}`}>
                {data.roles.map((r) => <option key={r} value={r}>{ROLE_TEXT[r] || r}</option>)}
              </select>
            </div>
          ))}
        </div>
      </main>
    </AppShell>
  );
}
