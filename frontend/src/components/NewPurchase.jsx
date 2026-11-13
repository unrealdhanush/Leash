import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Mail } from "lucide-react";
import { api } from "../api.js";
import { money } from "../format.js";

function planLines(plan) {
  const groups = {};
  plan.forEach((f) => (groups[f.label] ||= []).push(f));
  return Object.entries(groups).map(([label, flows]) => {
    const weeks = flows.map((f) => f.week);
    const timing = weeks.length === 1 ? `week ${weeks[0]}` : `×${weeks.length}, weeks ${weeks[0]}–${weeks[weeks.length - 1]}`;
    return { label, amount: flows[0].amount, timing };
  });
}

export default function NewPurchase({ live, onStart }) {
  const [context, setContext] = useState(null);
  const [auto, setAuto] = useState(false);
  const [starting, setStarting] = useState(false);
  useEffect(() => {
    api.context().then(setContext).catch(() => setContext(null));
  }, []);

  const start = async () => {
    setStarting(true);
    await onStart(auto);
    setStarting(false);
  };
  const policy = context?.policy;

  return (
    <section className="newp" data-testid="new-purchase">
      <h2>New purchase</h2>
      <p className="newp-lead">A vendor sent a quote. Hand it to the agent and it will take it from the email to a card that can only pay what was decided.</p>

      <h3><Mail size={13} /> Vendor quote <small className="mono">quotes/northwind.txt</small></h3>
      <pre className="email" data-testid="new-purchase-quote">{context ? context.quote_text.trim() : "Loading…"}</pre>

      {policy && (
        <>
          <h3>Spending policy</h3>
          <dl className="rules" data-testid="new-purchase-policy">
            <dt>The agent may spend alone up to</dt><dd className="mono">{money(policy.auto_approve_max)} {policy.currency} per charge</dd>
            <dt>Cash must stay above</dt><dd className="mono">{money(policy.reserve_floor)} {policy.currency}</dd>
            <dt>It looks ahead</dt><dd className="mono">{policy.horizon_weeks} weeks</dd>
          </dl>
          <h3>Cash plan</h3>
          <dl className="rules" data-testid="new-purchase-cash-plan">
            <dt>Starting cash</dt><dd className="mono">{money(context.operating_cash)} {policy.currency}</dd>
            {planLines(context.cash_plan).map((line) => (
              <React.Fragment key={line.label}>
                <dt>{line.label} <span className="dim">({line.timing})</span></dt>
                <dd className="mono">{line.amount > 0 ? "+" : "−"}{money(Math.abs(line.amount))}</dd>
              </React.Fragment>
            ))}
          </dl>
        </>
      )}

      <h3>When it needs a person</h3>
      <div className="seg" role="radiogroup" data-testid="approval-mode">
        <button role="radio" aria-checked={!auto} className={!auto ? "on" : ""} onClick={() => setAuto(false)} data-testid="approval-mode-manual">
          <b>I approve each one</b>
          <small>It stops and waits for {context?.approver || "you"}</small>
        </button>
        <button role="radio" aria-checked={auto} className={auto ? "on" : ""} onClick={() => setAuto(true)} data-testid="approval-mode-auto">
          <b>Auto answers</b>
          <small>Decline the cheaper out-of-policy plan, approve the price change</small>
        </button>
      </div>

      <button className="btn primary wide" onClick={start} disabled={Boolean(live) || starting} data-testid="start-run-btn">
        {live ? "A purchase is in progress" : starting ? "Handing over…" : <>Hand it to the agent <ArrowRight size={15} /></>}
      </button>
      {live && <p className="small dim">Only one purchase runs at a time. <Link to={`/app/purchases/${live.id}`} data-testid="open-live-purchase">Open #{live.seq}</Link></p>}
    </section>
  );
}
