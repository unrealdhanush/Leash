import React from "react";
import { summarize } from "../format.js";

const STATUS = {
  running: "Running",
  waiting_approval: "Waiting for you",
  done: "Finished",
  failed: "Stopped",
};

export default function TopBar({ run, events, auto, setAuto, onStart, health }) {
  const busy = run && (run.status === "running" || run.status === "waiting_approval");
  const s = summarize(events);
  return (
    <header className="topbar">
      <div className="brand">
        <span className="mark">L</span>
        <div>
          <h1>Leash</h1>
          <p>Purchase agent console · Airwallex sandbox</p>
        </div>
      </div>
      <div className="summary" data-testid="run-summary">
        <Stat label="Status" value={run ? STATUS[run.status] : "Idle"} tone={run?.status} testid="run-status" />
        <Stat label="Expected" value={`${s.expected}/${s.rows}`} tone="ok" testid="summary-expected" />
        <Stat label="Unexpected" value={s.unexpected} tone={s.unexpected ? "bad" : "ok"} testid="summary-unexpected" />
        {health && <Stat label="Model" value={health.model} testid="llm-model" small />}
      </div>
      <div className="controls">
        <label className="switch" data-testid="auto-approve-toggle">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} disabled={busy} data-testid="auto-approve-input" />
          <span className="track"><span className="thumb" /></span>
          <span className="switch-label">
            Auto answers
            <small>{auto ? "decline annual, approve price change" : "you approve each one"}</small>
          </span>
        </label>
        <button className="btn primary" onClick={onStart} disabled={busy} data-testid="start-run-btn">
          {busy ? "Run in progress" : run ? "Run again" : "Start run"}
        </button>
      </div>
    </header>
  );
}

function Stat({ label, value, tone, testid, small }) {
  return (
    <div className={`stat ${tone || ""} ${small ? "small" : ""}`}>
      <span>{label}</span>
      <b data-testid={testid}>{value}</b>
    </div>
  );
}
