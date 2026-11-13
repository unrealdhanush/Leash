import React from "react";
import { cardState, money } from "../format.js";
import Forecast from "./Forecast.jsx";

export default function SidePanel({ run, events, decide }) {
  const card = cardState(events);
  const last = [...events].reverse().find((e) => e.event === "assessments");
  const chosen = last?.items.find((a) => a.allowed) || last?.items[0];
  return (
    <aside className="side">
      {run?.pending && <ApprovalPanel req={run.pending} decide={decide} />}
      <CardPanel card={card} />
      <div className="panel" data-testid="forecast-panel">
        <h3>Cash forecast <small>{chosen ? `${chosen.quote.name} · 12 weeks` : ""}</small></h3>
        {chosen ? <Forecast balances={chosen.balances} breach={chosen.breach_week} /> : <p className="dim">Appears after the agent's first assessment.</p>}
      </div>
    </aside>
  );
}

function ApprovalPanel({ req, decide }) {
  const q = req.quote;
  return (
    <div className="panel approval" data-testid="approval-panel">
      <h3>Approval needed</h3>
      <dl>
        <dt>Vendor</dt><dd data-testid="approval-vendor">{req.vendor}</dd>
        <dt>Terms</dt><dd className="mono" data-testid="approval-terms">{money(q.charge)} {q.currency} ×{q.charges_per_year} per year ({q.name})</dd>
        <dt>Why</dt><dd><ul>{req.reasons.map((r) => <li key={r}>{r}</li>)}</ul></dd>
        <dt>Binds to</dt><dd className="mono dim">{req.digest.slice(0, 12)}</dd>
      </dl>
      <div className="actions">
        <button className="btn approve" onClick={() => decide(true, req.digest)} data-testid="approval-approve-btn">Approve</button>
        <button className="btn decline" onClick={() => decide(false, req.digest)} data-testid="approval-decline-btn">Decline</button>
      </div>
    </div>
  );
}

function CardPanel({ card }) {
  const status = card.status || "NOT ISSUED";
  return (
    <div className={`panel vcard ${status === "INACTIVE" ? "frozen" : ""}`} data-testid="card-panel">
      <div className="vcard-top">
        <span>Virtual card</span>
        <span className={`badge ${status === "ACTIVE" ? "expected" : status === "INACTIVE" ? "frozen" : "muted"}`} data-testid="card-status">
          {status === "INACTIVE" ? "FROZEN" : status}
        </span>
      </div>
      <div className="mono vcard-id" data-testid="card-id">{card.id || "—"}</div>
      <div className="vcard-grid">
        <span>Limit</span><b className="mono" data-testid="card-limit">{card.quote ? `${money(card.quote.charge)} ${card.quote.currency}` : "—"}</b>
        <span>Merchant</span><b className="mono">{card.quote ? `MCC ${card.quote.merchant_category}` : "—"}</b>
        {card.limits?.limits.map((l) => (
          <React.Fragment key={l.interval}>
            <span>{l.interval}</span><b className="mono">{money(l.remaining)} left</b>
          </React.Fragment>
        ))}
      </div>
      {card.reason && <p className="dim small">{card.reason}</p>}
    </div>
  );
}
