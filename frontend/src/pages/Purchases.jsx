import React, { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeftRight, Check, X } from "lucide-react";
import { api } from "../api.js";
import { ACTIVE, planText, when } from "../format.js";
import AppShell, { CardBadge, StatusPill } from "../components/AppShell.jsx";
import NewPurchase from "../components/NewPurchase.jsx";

export default function Purchases() {
  const [runs, setRuns] = useState(null);
  const [picked, setPicked] = useState([]);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  const load = useCallback(() => api.runs().then(setRuns).catch((e) => setError(e.message)), []);
  useEffect(() => {
    load();
  }, [load]);

  const live = runs?.find((r) => ACTIVE.includes(r.status));
  useEffect(() => {
    if (!live) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [live?.id, load]);

  const start = async (body) => {
    setError(null);
    try {
      const snap = await api.start(body);
      navigate(`/app/purchases/${snap.id}`);
    } catch (e) {
      setError(e.message);
      load();
    }
  };
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id].slice(-2)));

  return (
    <AppShell>
      {error && <div className="banner error" data-testid="app-error">{error}</div>}
      <main className="home">
        <NewPurchase live={live} onStart={start} />
        <section className="history" data-testid="purchase-history">
          <div className="history-head">
            <h2>Purchases <span className="mono dim" data-testid="purchase-count">{runs?.length ?? ""}</span></h2>
            <button
              className="btn"
              disabled={picked.length !== 2}
              onClick={() => navigate(`/app/compare?a=${picked[0]}&b=${picked[1]}`)}
              data-testid="compare-btn"
            >
              <ArrowLeftRight size={14} /> {picked.length === 2 ? "Compare the two" : `Pick two to compare (${picked.length}/2)`}
            </button>
          </div>
          {runs?.length === 0 && (
            <div className="empty" data-testid="history-empty">
              <h2>Nothing bought yet</h2>
              <p>Every purchase the agent handles is kept here, with its full timeline, so you can reopen it or put two side by side.</p>
            </div>
          )}
          <div className="plist">
            {runs?.map((r) => <PurchaseRow key={r.id} run={r} picked={picked.includes(r.id)} onPick={() => toggle(r.id)} />)}
          </div>
        </section>
      </main>
    </AppShell>
  );
}

function PurchaseRow({ run, picked, onPick }) {
  const s = run.summary;
  return (
    <div className={`prow ${picked ? "picked" : ""}`} data-testid={`purchase-row-${run.id}`}>
      <label className="pick" title="Pick to compare">
        <input type="checkbox" checked={picked} onChange={onPick} data-testid={`purchase-pick-${run.id}`} />
        <span className="box">{picked && <Check size={12} />}</span>
      </label>
      <Link to={`/app/purchases/${run.id}`} className="prow-main" data-testid={`purchase-open-${run.id}`}>
        <span className="mono dim">#{run.seq}</span>
        <span className="prow-vendor">
          <b>{s.vendor || "Reading the quote…"}</b>
          <small className="mono">{planText(s.plan)}</small>
        </span>
        <StatusPill status={run.status} testid={`purchase-status-${run.id}`} />
        <CardBadge status={s.card_status} />
        <span className="prow-approvals" title="Approvals asked">
          {s.approvals.map((a, i) => (
            <span key={i} className={`tick ${a.approved ? "ok" : a.approved === false ? "bad" : ""}`}>
              {a.approved ? <Check size={12} /> : a.approved === false ? <X size={12} /> : "?"}
            </span>
          ))}
        </span>
        <span className={`mono ${s.unexpected ? "warn" : ""}`} data-testid={`purchase-checks-${run.id}`}>{s.rows - s.unexpected}/{s.rows}</span>
        <span className="dim small">{run.quote_source === "own" ? "own quote · " : ""}{run.auto ? "auto" : "manual"} · {when(run.started_at)}</span>
      </Link>
    </div>
  );
}
