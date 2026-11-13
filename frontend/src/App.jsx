import React, { useEffect, useState } from "react";
import { api } from "./api.js";
import { useRun } from "./useRun.js";
import TopBar from "./components/TopBar.jsx";
import Timeline from "./components/Timeline.jsx";
import RawStream from "./components/RawStream.jsx";
import SidePanel from "./components/SidePanel.jsx";

export default function App() {
  const { run, events, error, start, decide } = useRun();
  const [auto, setAuto] = useState(false);
  const [view, setView] = useState("visual");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="app" data-testid="leash-console">
      <TopBar run={run} events={events} auto={auto} setAuto={setAuto} onStart={() => start(auto)} health={health} />
      {error && <div className="banner error" data-testid="app-error">{error}</div>}
      <main className="grid">
        <section className="stream">
          <div className="tabs" role="tablist">
            <button data-testid="view-visual-tab" className={view === "visual" ? "on" : ""} onClick={() => setView("visual")}>Timeline</button>
            <button data-testid="view-raw-tab" className={view === "raw" ? "on" : ""} onClick={() => setView("raw")}>Raw JSON stream</button>
            <span className="count" data-testid="event-count">{events.length} events</span>
          </div>
          {view === "visual" ? <Timeline events={events} run={run} /> : <RawStream events={events} />}
        </section>
        <SidePanel run={run} events={events} decide={decide} />
      </main>
    </div>
  );
}
