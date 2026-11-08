"""Leash purchase agent: compare quotes, issue a card that matches the decision, prove it holds."""

import os

from leash.client import AirwallexClient, new_request_id
from leash.policy import Policy, Quote, card_controls, decide
from leash.sandbox import CardSimulator

QUOTES = [
    Quote(name="monthly", charge=1000.00, charges_per_year=12, currency="USD"),
    Quote(name="annual", charge=9840.00, charges_per_year=1, currency="USD"),  # 18% off 12 x 1000
]
POLICY = Policy(auto_approve_max=5000.00, reserve_floor=50000.00)


def cash_available(client: AirwallexClient, currency: str) -> float:
    for balance in client.get("/api/v1/balances/current"):
        if balance["currency"] == currency:
            return balance["available_amount"]
    return 0.0


def get_or_create_cardholder(client: AirwallexClient, email: str) -> str:
    existing = client.get("/api/v1/issuing/cardholders", params={"email": email})["items"]
    if existing:
        return existing[0]["cardholder_id"]
    # REST calls this field `type`; the MCP tool calls it `cardholder_type`.
    created = client.post(
        "/api/v1/issuing/cardholders/create",
        {"type": "DELEGATE", "email": email},
        request_id=new_request_id(),
    )
    return created["cardholder_id"]


def issue_card(client: AirwallexClient, cardholder_id: str, quote: Quote, created_by: str) -> str:
    card = client.post(
        "/api/v1/issuing/cards/create",
        {
            "cardholder_id": cardholder_id,
            "created_by": created_by,
            "form_factor": "VIRTUAL",
            "is_personalized": False,
            "program": {"purpose": "COMMERCIAL"},
            "purpose": "SUBSCRIPTIONS",
            "nick_name": f"Leash SaaS {quote.name}",
            "authorization_controls": card_controls(quote),
            "metadata": {"decision": quote.name, "charge": f"{quote.charge} {quote.currency}"},
        },
        request_id=new_request_id(),
    )
    return card["card_id"]


def main():
    email = os.environ.get("LEASH_CARDHOLDER_EMAIL")
    created_by = os.environ.get("LEASH_CREATED_BY")
    if not email or not created_by:
        raise SystemExit("Set LEASH_CARDHOLDER_EMAIL and LEASH_CREATED_BY in .env")

    client = AirwallexClient.from_env()

    cash = cash_available(client, POLICY.currency)
    decision = decide(QUOTES, cash, POLICY)
    print(f"Cash available: {cash:,.2f} {POLICY.currency}")
    for a in decision.assessments:
        verdict = "ok" if a.allowed else "; ".join(a.reasons)
        print(f"  {a.quote.name:8} {a.quote.charge:>10,.2f} x{a.quote.charges_per_year:<2} -> {verdict}")
    if decision.chosen is None:
        raise SystemExit("No quote passes policy; escalate to a human.")
    quote = decision.chosen
    print(f"Decision: {quote.name}")

    cardholder_id = get_or_create_cardholder(client, email)
    card_id = issue_card(client, cardholder_id, quote, created_by)
    print(f"Card issued: {card_id}")

    sim = CardSimulator(client)
    for label, amount, should_clear in [
        ("over limit", round(quote.charge + 0.01, 2), False),
        ("at limit", quote.charge, True),
    ]:
        result = sim.authorize(card_id, amount, quote.currency)
        outcome = "cleared" if result.accepted else f"declined ({result.failure_reason})"
        check = "as expected" if result.accepted == should_clear else "UNEXPECTED"
        print(f"  {label:10} {amount:>10,.2f} -> {outcome} [{check}]")

    limits = client.get(f"/api/v1/issuing/cards/{card_id}/limits")
    print("Remaining limits:")
    for limit in limits["limits"]:
        print(f"  {limit['interval']:15} {limit['remaining']:>10,.2f} of {limit['amount']:,.2f} {limits['currency']}")


if __name__ == "__main__":
    main()
