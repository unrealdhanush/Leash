import React, { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { STATUS, duration, money, planText, when } from "../format.js";
import AppShell from "../components/AppShell.jsx";
import { outcomeOf } from "../components/Rows.jsx";

const answer = (a) => (a.approved ? "approved" : a.approved === false ? "declined" : "no answer");

// Rows of [section, label, valueA, valueB, comparable].
function buildRows(a, b) {
  const pair = (fn) => [fn(a), fn(b)];
  const rows = [
    ["Outcome", "Status", ...pair((r) => STATUS[r.status]), true],
    ["Outcome", "Approvals answered by", ...pair((r) => (r.auto ? "auto answers" : "a person")), true],
    ["Outcome", "Plan picked by policy", ...pair((r) => r.summary.chosen || "—"), true],
    ["Outcome", "Plan on the card", ...pair((r) => planText(r.summary.plan)), true],
    ["Outcome", "Card at the end", ...pair((r) => (r.summary.card_status === "INACTIVE" ? "FROZEN" : r.summary.card_status || "no card")), true],
    ["Outcome", "Results as expected", ...pair((r) => `${r.summary.rows - r.summary.unexpected}/${r.summary.rows}`), true],
    ["Outcome", "Time taken", ...pair((r) => duration(r.started_at, r.finished_at)), false],
    ["Outcome", "Model", ...pair((r) => r.model), true],
  ];
  const asked = Math.max(a.summary.approvals.length, b.summary.approvals.length);
  for (let i = 0; i < asked; i++) {
    const text = (r) => {
      const ap = r.summary.approvals[i];
      return ap ? `${ap.quote.name} ${money(ap.quote.charge)} ${ap.quote.currency} ×${ap.quote.charges_per_year}: ${answer(ap)}` : "not asked";
    };
    rows.push(["Approvals", `Approval ${i + 1}`, ...pair(text), true]);
  }
  const checks = (r) => r.events.filter((e) => e.event === "charge" || e.event === "checkout");
  const labels = [...new Set([...checks(a), ...checks(b)].map((e) => e.label))];
  labels.forEach((label) => {
    const text = (r) => {
      const e = checks(r).find((x) => x.label === label);
      return e ? `${outcomeOf(e)[0]}${e.as_expected ? "" : " (UNEXPECTED)"}` : "did not happen";
    };
    rows.push(["Charges and checkouts", label, ...pair(text), true]);
  });
  return rows;
}

export default function Compare() {
  const [params, setParams] = useSearchParams();
  const [runs, setRuns] = useState([]);
  const [pair, setPair] = useState(null);
  const [error, setError] = useState(null);
  const a = params.get("a");
  const b = params.get("b");

  useEffect(() => {
    api.runs().then(setRuns).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!a || !b) return;
    setPair(null);
    Promise.all([api.run(a), api.run(b)]).then(setPair).catch((e) => setError(e.message));
  }, [a, b]);

  const rows = pair ? buildRows(...pair) : [];
  const differences = rows.filter((r) => r[4] && r[2] !== r[3]).length;
  const pick = (side) => (
    <select value={side === "a" ? a || "" : b || ""} onChange={(e) => setParams({ a, b, [side]: e.target.value })} data-testid={`compare-select-${side}`}>
      {runs.map((r) => <option key={r.id} value={r.id}>#{r.seq} · {r.summary.vendor || "no vendor"} · {when(r.started_at)}</option>)}
    </select>
  );

  return (
    <AppShell>
      <main className="page compare" data-testid="compare-page">
        <p className="crumb"><Link to="/app" data-testid="back-to-purchases">Purchases</Link> / Compare</p>
        <h1>Two purchases, side by side</h1>
        {error && <div className="banner error" data-testid="app-error">{error}</div>}
        {(!a || !b) && <p className="dim">Pick two purchases from the <Link to="/app">list</Link> to compare them.</p>}
        {pair && (
          <>
            <p className="cmp-verdict" data-testid="compare-differences">
              {differences === 0 ? "These two purchases ended the same way." : `${differences} ${differences === 1 ? "difference" : "differences"}, marked below.`}
            </p>
            <div className="cmp" data-testid="compare-table">
              <div className="cmp-row cmp-head">
                <span />
                {pair.map((r, i) => (
                  <span key={i} className="cmp-pick">
                    {pick(i === 0 ? "a" : "b")}
                    <Link to={`/app/purchases/${r.id}`} data-testid={`compare-open-${i === 0 ? "a" : "b"}`}>Open timeline</Link>
                  </span>
                ))}
              </div>
              {rows.map(([section, label, va, vb, comparable], i) => (
                <React.Fragment key={section + label}>
                  {(i === 0 || rows[i - 1][0] !== section) && <div className="cmp-section">{section}</div>}
                  <div className={`cmp-row ${comparable && va !== vb ? "diff" : ""}`} data-testid={`compare-row-${i}`}>
                    <span className="cmp-label">{label}</span>
                    <span className="mono">{va}</span>
                    <span className="mono">{vb}</span>
                  </div>
                </React.Fragment>
              ))}
              <div className="cmp-section">How the agent explained the decision</div>
              <div className="cmp-row cmp-text">
                <span className="cmp-label">Explanation</span>
                {pair.map((r, i) => <p key={i} data-testid={`compare-explanation-${i === 0 ? "a" : "b"}`}>{r.events.find((e) => e.event === "decision")?.explanation || "—"}</p>)}
              </div>
            </div>
          </>
        )}
      </main>
    </AppShell>
  );
}
