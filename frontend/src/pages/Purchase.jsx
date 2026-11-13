import React, { useCallback, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useRun } from "../useRun.js";
import { cardState, duration, groupScenes, planText, summarize, when } from "../format.js";
import AppShell, { StatusPill } from "../components/AppShell.jsx";
import SceneRail from "../components/SceneRail.jsx";
import Timeline from "../components/Timeline.jsx";
import RawStream from "../components/RawStream.jsx";
import SidePanel from "../components/SidePanel.jsx";

export default function Purchase() {
  const { id } = useParams();
  const { run, events, error, decide } = useRun(id);
  const [view, setView] = useState("visual");

  const jump = useCallback((key) => {
    setView("visual");
    setTimeout(() => document.getElementById(`chapter-${key}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }, []);

  if (!run) {
    return (
      <AppShell>
        <div className="page">
          {error ? <div className="banner error" data-testid="app-error">{error} <Link to="/app">Back to purchases</Link></div> : <p className="dim" data-testid="purchase-loading">Loading…</p>}
        </div>
      </AppShell>
    );
  }

  const scenes = groupScenes(events);
  return (
    <AppShell>
      <PurchaseHeader run={run} events={events} />
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
    </AppShell>
  );
}

function PurchaseHeader({ run, events }) {
  const s = summarize(events);
  const card = cardState(events);
  const vendor = events.find((e) => e.event === "quotes_read")?.vendor;
  return (
    <header className="phead" data-testid="purchase-header">
      <div className="phead-main">
        <p className="crumb"><Link to="/app" data-testid="back-to-purchases">Purchases</Link> / <span className="mono">#{run.seq}</span></p>
        <h1 data-testid="purchase-vendor">{vendor || "New purchase"}</h1>
        <p className="phead-meta">
          <span data-testid="purchase-plan">{card.quote ? `On the card: ${planText(card.quote)}` : "No card yet"}</span>
          <span>{run.auto ? "Auto answers" : "You approve each one"}</span>
          <span>Started {when(run.started_at)}</span>
          {run.finished_at && <span>Took {duration(run.started_at, run.finished_at)}</span>}
        </p>
      </div>
      <div className="summary" data-testid="run-summary">
        <div className="stat"><span>Status</span><StatusPill status={run.status} testid="run-status" /></div>
        <div className="stat ok"><span>As expected</span><b data-testid="summary-expected">{s.expected}/{s.rows}</b></div>
        <div className={`stat ${s.unexpected ? "bad" : "ok"}`}><span>Unexpected</span><b data-testid="summary-unexpected">{s.unexpected}</b></div>
      </div>
    </header>
  );
}
