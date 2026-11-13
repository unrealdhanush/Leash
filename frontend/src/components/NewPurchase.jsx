import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Mail, Upload } from "lucide-react";
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

function OwnQuote({ quote, setQuote, increase, setIncrease, policy, mcc }) {
  const file = useRef(null);
  const [note, setNote] = useState(null);
  const [showIncrease, setShowIncrease] = useState(false);

  const upload = async (e) => {
    const picked = e.target.files[0];
    e.target.value = "";
    if (!picked) return;
    setNote({ text: `Reading ${picked.name}…` });
    try {
      const out = await api.extract(picked);
      setQuote(out.text);
      setNote({ text: `Loaded ${picked.name}. Check the text below before you hand it over.` });
    } catch (err) {
      setNote({ text: err.message, bad: true });
    }
  };

  return (
    <div className="own" data-testid="own-quote">
      <textarea
        value={quote}
        onChange={(e) => setQuote(e.target.value)}
        placeholder="Paste the vendor's email or quote here"
        maxLength={20000}
        rows={9}
        data-testid="own-quote-text"
      />
      <div className="own-row">
        <input ref={file} type="file" accept=".txt,.eml,.md,.pdf,text/plain,application/pdf" hidden onChange={upload} data-testid="own-quote-file" />
        <button className="btn small-btn" onClick={() => file.current.click()} data-testid="own-quote-upload-btn"><Upload size={13} /> Upload a text, email or PDF file</button>
        <button className="linkish" onClick={() => setShowIncrease((v) => !v)} data-testid="own-increase-toggle">
          {showIncrease ? "Remove the price-change email" : "Add a later price-change email"}
        </button>
      </div>
      {note && <p className={`small ${note.bad ? "bad-text" : "dim"}`} data-testid="own-quote-note">{note.text}</p>}
      {showIncrease && (
        <textarea
          value={increase}
          onChange={(e) => setIncrease(e.target.value)}
          placeholder="Optional: the vendor's later email with a new price. Leave empty and the price-rise chapter is left out."
          maxLength={20000}
          rows={5}
          data-testid="own-increase-text"
        />
      )}
      <p className="small dim own-hint" data-testid="own-quote-hint">
        The quote needs at least two ways to pay for the same plan (for example monthly and annual), each with its price written out.
        Policy allows {policy?.currency || "USD"} only, and the card is issued for software merchants (MCC {mcc}).
        If the agent cannot read it, the purchase stops and says why.
      </p>
    </div>
  );
}

export default function NewPurchase({ live, onStart }) {
  const [context, setContext] = useState(null);
  const [auto, setAuto] = useState(false);
  const [own, setOwn] = useState(false);
  const [quote, setQuote] = useState("");
  const [increase, setIncrease] = useState("");
  const [starting, setStarting] = useState(false);
  useEffect(() => {
    api.context().then(setContext).catch(() => setContext(null));
  }, []);

  const start = async () => {
    setStarting(true);
    await onStart(own ? { auto, quote_text: quote.trim(), increase_text: increase.trim() || null } : { auto });
    setStarting(false);
  };
  const policy = context?.policy;
  const tooShort = own && quote.trim().length < 20;

  return (
    <section className="newp" data-testid="new-purchase">
      <h2>New purchase</h2>
      <p className="newp-lead">A vendor sent a quote. Hand it to the agent and it will take it from the email to a card that can only pay what was decided.</p>

      <h3><Mail size={13} /> Vendor quote {!own && <small className="mono">quotes/northwind.txt</small>}</h3>
      <div className="seg slim" role="radiogroup" data-testid="quote-source">
        <button role="radio" aria-checked={!own} className={!own ? "on" : ""} onClick={() => setOwn(false)} data-testid="quote-source-example"><b>Example quote</b></button>
        <button role="radio" aria-checked={own} className={own ? "on" : ""} onClick={() => setOwn(true)} data-testid="quote-source-own"><b>My own quote</b></button>
      </div>
      {own
        ? <OwnQuote quote={quote} setQuote={setQuote} increase={increase} setIncrease={setIncrease} policy={policy} mcc={context?.merchant_category} />
        : <pre className="email" data-testid="new-purchase-quote">{context ? context.quote_text.trim() : "Loading…"}</pre>}

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
          <small>Decline the first request, approve the second</small>
        </button>
      </div>

      <button className="btn primary wide" onClick={start} disabled={Boolean(live) || starting || tooShort} data-testid="start-run-btn">
        {live ? "A purchase is in progress" : starting ? "Handing over…" : <>Hand it to the agent <ArrowRight size={15} /></>}
      </button>
      {tooShort && !live && <p className="small dim">Paste or upload a quote first.</p>}
      {live && <p className="small dim">Only one purchase runs at a time. <Link to={`/app/purchases/${live.id}`} data-testid="open-live-purchase">Open #{live.seq}</Link></p>}
    </section>
  );
}
