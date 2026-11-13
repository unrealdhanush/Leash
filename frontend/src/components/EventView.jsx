import React from "react";
import { money } from "../format.js";
import Assessments from "./Assessments.jsx";
import { ChargeRow, CheckoutRow } from "./Rows.jsx";

export default function EventView({ e }) {
  const id = `event-${e._i}`;
  switch (e.event) {
    case "info":
      return <p className="info" data-testid={id}>{e.text}</p>;
    case "error":
      return <div className="banner error" data-testid="run-error">Run stopped: {e.text}</div>;
    case "quote_text":
      return <pre className="email" data-testid={id}>{e.text.trim()}</pre>;
    case "quotes_read":
      return <QuotesRead e={e} id={id} />;
    case "cash":
      return (
        <div className="kv" data-testid={id}>
          <span>Live {e.currency} cash</span><b className="mono" data-testid="cash-available">{money(e.available)}</b>
          <span>Reserve floor</span><b className="mono">{money(e.reserve_floor)}</b>
        </div>
      );
    case "assessments":
      return <Assessments items={e.items} id={id} />;
    case "decision":
      return (
        <div className="decision" data-testid="decision">
          <div className="decision-head">Decision <b data-testid="decision-chosen">{e.chosen}</b></div>
          <p data-testid="decision-explanation"><span className="who">Agent</span>{e.explanation}</p>
        </div>
      );
    case "approval_request":
      return (
        <div className="approval-log" data-testid={id}>
          <b>Approval needed</b> · {e.vendor} · {money(e.quote.charge)} {e.quote.currency} ×{e.quote.charges_per_year} ({e.quote.name})
          <ul>{e.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          <span className="mono dim">binds to {e.digest.slice(0, 12)}</span>
        </div>
      );
    case "approval_result":
      return (
        <p className={`verdict ${e.approved ? "ok" : "bad"}`} data-testid={`approval-result-${e._i}`}>
          {e.approver}: {e.approved ? "approved" : "declined"}
        </p>
      );
    case "card_issued":
      return (
        <div className="kv" data-testid="card-issued">
          <span>Virtual card</span><b className="mono">{e.card_id}</b>
          <span>Controls</span>
          <b>{money(e.quote.charge)} per charge and per period · {e.quote.currency} only · MCC {e.quote.merchant_category} only</b>
        </div>
      );
    case "card_updated":
      return <p className="info" data-testid="card-updated">Card limit raised to <b className="mono">{money(e.quote.charge)}</b> under approval <span className="mono">{e.approval}</span></p>;
    case "card_status":
      return <p className={`verdict ${e.status === "INACTIVE" ? "frozen" : "ok"}`} data-testid={`card-status-${e._i}`}>Card {e.status}: {e.reason}</p>;
    case "charge":
      return <ChargeRow e={e} />;
    case "checkout":
      return <CheckoutRow e={e} />;
    case "deposit":
      return <p className="info" data-testid="deposit">Deposit from {e.payer}: <b className="mono">{money(e.amount)} {e.currency}</b> ({e.status})</p>;
    case "limits":
      return (
        <table className="table" data-testid="limits-table">
          <thead><tr><th>Interval</th><th>Remaining</th><th>Limit</th></tr></thead>
          <tbody>
            {e.limits.map((l) => (
              <tr key={l.interval}><td>{l.interval}</td><td className="mono">{money(l.remaining)}</td><td className="mono">{money(l.amount)} {e.currency}</td></tr>
            ))}
          </tbody>
        </table>
      );
    default:
      return <pre className="raw-line">{JSON.stringify(e)}</pre>;
  }
}

function QuotesRead({ e, id }) {
  return (
    <div data-testid={id}>
      <p className="info">Agent read <b data-testid="quotes-count">{e.quotes.length}</b> options from <b>{e.vendor}</b></p>
      <table className="table" data-testid="quotes-table">
        <thead><tr><th>Option</th><th>Per charge</th><th>Charges / yr</th><th>Annual</th></tr></thead>
        <tbody>
          {e.quotes.map((q) => (
            <tr key={q.name} data-testid={`quote-row-${q.name}`}>
              <td>{q.name}</td>
              <td className="mono">{money(q.charge)} {q.currency}</td>
              <td className="mono">×{q.charges_per_year}</td>
              <td className="mono">{money(q.annual_cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
