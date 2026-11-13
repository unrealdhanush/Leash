import React, { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Check, Copy, Download, Link2 } from "lucide-react";
import { api } from "../api.js";
import { useRun } from "../useRun.js";
import { ACTIVE, cardState, duration, groupScenes, planText, summarize, when } from "../format.js";
import AppShell, { StatusPill } from "../components/AppShell.jsx";
import SceneRail from "../components/SceneRail.jsx";
import Timeline from "../components/Timeline.jsx";
import RawStream from "../components/RawStream.jsx";
import SidePanel from "../components/SidePanel.jsx";

export default function Purchase() {
  const { id } = useParams();
  const { run, events, error, decide } = useRun(id);
  if (!run) {
    return (
      <AppShell>
        <div className="page">
          {error ? <div className="banner error" data-testid="app-error">{error} <Link to="/app">Back to purchases</Link></div> : <p className="dim" data-testid="purchase-loading">Loading…</p>}
        </div>
      </AppShell>
    );
  }
  return <AppShell><PurchaseView run={run} events={events} error={error} decide={decide} /></AppShell>;
}

export function PurchaseView({ run, events, error, decide, readOnly }) {
  const [view, setView] = useState("visual");
  const jump = useCallback((key) => {
    setView("visual");
    setTimeout(() => document.getElementById(`chapter-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }, []);
  const scenes = groupScenes(events);
  return (
    <>
      <PurchaseHeader run={run} events={events} readOnly={readOnly} />
      {error && <div className="banner error" data-testid="app-error">{error}</div>}
      {run.status === "interrupted" && <div className="banner error" data-testid="run-interrupted">{run.error}</div>}
      <main className="detail">
        <SceneRail scenes={scenes} run={run} onJump={jump} />
        <section className="stream">
          <div className="tabs" role="tablist">
            <button data-testid="view-visual-tab" className={view === "visual" ? "on" : ""} onClick={() => setView("visual")}>Timeline</button>
            <button data-testid="view-raw-tab" className={view === "raw" ? "on" : ""} onClick={() => setView("raw")}>Raw JSON stream</button>
            <span className="count" data-testid="event-count">{events.length} events</span>
          </div>
          {view === "visual" ? <Timeline scenes={scenes} run={run} /> : <RawStream events={events} />}
        </section>
        <SidePanel run={run} events={events} decide={decide} />
      </main>
    </>
  );
}

function PurchaseHeader({ run, events, readOnly }) {
  const s = summarize(events);
  const card = cardState(events);
  const vendor = events.find((e) => e.event === "quotes_read")?.vendor;
  return (
    <header className="phead" data-testid="purchase-header">
      <div className="phead-main">
        <p className="crumb">
          {readOnly ? "Shared purchase" : <Link to="/app" data-testid="back-to-purchases">Purchases</Link>} / <span className="mono">#{run.seq}</span>
        </p>
        <h1 data-testid="purchase-vendor">{vendor || "New purchase"}</h1>
        <p className="phead-meta">
          <span data-testid="purchase-plan">{card.quote ? `On the card: ${planText(card.quote)}` : "No card yet"}</span>
          <span data-testid="purchase-quote-source">{run.quote_source === "own" ? "Own quote" : "Example quote"}</span>
          <span>{run.auto ? "Auto answers" : "A person approves each one"}</span>
          <span>Started {when(run.started_at)}</span>
          {run.finished_at && <span>Took {duration(run.started_at, run.finished_at)}</span>}
        </p>
        {!readOnly && !ACTIVE.includes(run.status) && <Actions run={run} />}
      </div>
      <div className="summary" data-testid="run-summary">
        <div className="stat"><span>Status</span><StatusPill status={run.status} testid="run-status" /></div>
        <div className="stat ok"><span>As expected</span><b data-testid="summary-expected">{s.expected}/{s.rows}</b></div>
        <div className={`stat ${s.unexpected ? "bad" : "ok"}`}><span>Unexpected</span><b data-testid="summary-unexpected">{s.unexpected}</b></div>
      </div>
    </header>
  );
}

function Actions({ run }) {
  const [token, setToken] = useState(run.share_token);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);
  const url = token ? `${window.location.origin}/share/${token}` : "";

  const share = async () => {
    setError(null);
    try {
      if (!token) setToken((await api.share(run.id)).token);
      setOpen((v) => !v || !token);
    } catch (e) {
      setError(e.message);
    }
  };
  const copy = async () => {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const turnOff = async () => {
    await api.unshare(run.id);
    setToken(null);
    setOpen(false);
  };

  return (
    <div className="phead-actions">
      <a className="btn small-btn" href={api.exportUrl(run.id)} download data-testid="export-btn"><Download size={13} /> Download the event trail</a>
      <button className={`btn small-btn ${token ? "lit" : ""}`} onClick={share} data-testid="share-btn"><Link2 size={13} /> {token ? "Share link is on" : "Create a share link"}</button>
      {error && <span className="small bad-text" data-testid="share-error">{error}</span>}
      {open && token && (
        <div className="share-pop" data-testid="share-panel">
          <div className="share-url">
            <input readOnly value={url} onFocus={(e) => e.target.select()} data-testid="share-url" />
            <button className="btn small-btn" onClick={copy} data-testid="share-copy-btn">{copied ? <><Check size={13} /> Copied</> : <><Copy size={13} /> Copy</>}</button>
          </div>
          <p className="small dim">
            Anyone with this link can read this purchase, including the quote email, the card ID and the approver's name. They cannot approve, start or change anything.
          </p>
          <button className="linkish bad-text" onClick={turnOff} data-testid="share-off-btn">Turn the link off</button>
        </div>
      )}
    </div>
  );
}
