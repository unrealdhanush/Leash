import React from "react";
import { money } from "../format.js";
import Forecast from "./Forecast.jsx";

export default function Assessments({ items, id }) {
  return (
    <div className="assessments" data-testid={id}>
      {items.map((a) => (
        <div className="assess" key={a.quote.name + a.low_point} data-testid={`assessment-${a.quote.name}`}>
          <div className="assess-head">
            <b>{a.quote.name}</b>
            <span className="mono">{money(a.quote.charge)} {a.quote.currency}</span>
            <span className="mono dim">low point {money(a.low_point)}</span>
            <span className={`badge ${a.allowed ? "expected" : "unexpected-soft"}`}>{a.allowed ? "within policy" : "breaks policy"}</span>
          </div>
          {!a.allowed && <p className="reasons">{a.reasons.join("; ")}</p>}
          <Forecast balances={a.balances} breach={a.breach_week} height={110} />
        </div>
      ))}
    </div>
  );
}
