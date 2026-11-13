import React from "react";
import { money, slug } from "../format.js";

function Check({ ok, testid }) {
  return <span className={`badge ${ok ? "expected" : "unexpected"}`} data-testid={testid}>{ok ? "as expected" : "UNEXPECTED"}</span>;
}

// Outcome text and tone for a charge or checkout event.
export function outcomeOf(e) {
  if (e.event === "charge") return e.accepted ? ["cleared", "ok"] : [`declined ${e.failure_reason || ""}`.trim(), "bad"];
  if (!e.verified) return [`rejected by merchant: ${e.rejection}`, "bad"];
  if (e.accepted) return ["verified · card charged", "ok"];
  return [`verified · card declined ${e.failure_reason}`, "bad"];
}

export function ChargeRow({ e }) {
  const id = `charge-${slug(e.label)}`;
  const [outcome, tone] = outcomeOf(e);
  return (
    <div className={`row ${e.as_expected ? "" : "flag"}`} data-testid={id}>
      <span className="label">{e.label}</span>
      <span className="mono amt">{money(e.amount)} {e.currency}</span>
      <span className="mono dim">MCC {e.merchant_category}</span>
      <span className={`outcome ${tone}`}>{outcome}</span>
      <Check ok={e.as_expected} testid={`${id}-check`} />
    </div>
  );
}

export function CheckoutRow({ e }) {
  const id = `checkout-${slug(e.label)}`;
  const [outcome, tone] = outcomeOf(e);
  return (
    <div className={`row checkout ${e.as_expected ? "" : "flag"}`} data-testid={id}>
      <span className="label">{e.label}</span>
      <span className="mono amt">{money(e.amount)} {e.currency}</span>
      <span className={`outcome ${tone}`}>{outcome}</span>
      <Check ok={e.as_expected} testid={`${id}-check`} />
    </div>
  );
}
