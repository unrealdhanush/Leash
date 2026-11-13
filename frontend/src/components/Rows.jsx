import React from "react";
import { money, slug } from "../format.js";

function Check({ ok, testid }) {
  return <span className={`badge ${ok ? "expected" : "unexpected"}`} data-testid={testid}>{ok ? "as expected" : "UNEXPECTED"}</span>;
}

export function ChargeRow({ e }) {
  const id = `charge-${slug(e.label)}`;
  return (
    <div className={`row ${e.as_expected ? "" : "flag"}`} data-testid={id}>
      <span className="label">{e.label}</span>
      <span className="mono amt">{money(e.amount)} {e.currency}</span>
      <span className="mono dim">MCC {e.merchant_category}</span>
      <span className={`outcome ${e.accepted ? "ok" : "bad"}`}>{e.accepted ? "cleared" : `declined ${e.failure_reason || ""}`}</span>
      <Check ok={e.as_expected} testid={`${id}-check`} />
    </div>
  );
}

export function CheckoutRow({ e }) {
  const id = `checkout-${slug(e.label)}`;
  let outcome, tone;
  if (!e.verified) [outcome, tone] = [`rejected by merchant: ${e.rejection}`, "bad"];
  else if (e.accepted) [outcome, tone] = ["verified · card charged", "ok"];
  else [outcome, tone] = [`verified · card declined ${e.failure_reason}`, "bad"];
  return (
    <div className={`row ${e.as_expected ? "" : "flag"}`} data-testid={id}>
      <span className="label">{e.label}</span>
      <span className="mono amt">{money(e.amount)} {e.currency}</span>
      <span className={`outcome ${tone}`}>{outcome}</span>
      <Check ok={e.as_expected} testid={`${id}-check`} />
    </div>
  );
}
