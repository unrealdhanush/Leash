"""Wallet balances, deposits, and the demo setup that sizes USD cash like a real startup's."""

from leash.client import AirwallexClient, new_request_id

PARKING_CURRENCY = "EUR"  # where surplus sandbox USD is moved so the forecast has something to protect
MAX_CONVERSION = 1_000_000  # sandbox rejects larger single conversions with amount_above_limit


def cash_available(client: AirwallexClient, currency: str) -> float:
    for balance in client.get("/api/v1/balances/current"):
        if balance["currency"] == currency:
            return balance["available_amount"]
    return 0.0


def set_operating_cash(client: AirwallexClient, currency: str, target: float) -> list[dict]:
    """Convert to or from PARKING_CURRENCY until exactly `target` of `currency` is available. Sandbox only."""
    conversions = []
    gap = round(cash_available(client, currency) - target, 2)
    while abs(gap) >= 1:
        amount = min(abs(gap), MAX_CONVERSION)
        if gap > 0:  # surplus: sell `currency`
            body = {"sell_currency": currency, "buy_currency": PARKING_CURRENCY, "sell_amount": f"{amount:.2f}"}
        else:  # shortfall: buy `currency`
            body = {"sell_currency": PARKING_CURRENCY, "buy_currency": currency, "buy_amount": f"{amount:.2f}"}
        body |= {"reason": "Leash demo: set operating cash", "term_agreement": True}
        conversions.append(client.post("/api/v1/fx/conversions/create", body, request_id=new_request_id()))
        gap = round(gap - amount if gap > 0 else gap + amount, 2)
    return conversions


def global_account_id(client: AirwallexClient, currency: str) -> str:
    for account in client.get("/api/v1/global_accounts")["items"]:
        if any(f["currency"] == currency for f in account.get("required_features", [])):
            return account["id"]
    raise LookupError(f"no global account receives {currency}")


def simulate_deposit(client: AirwallexClient, account_id: str, amount: float, payer: str, reference: str) -> dict:
    # The simulation endpoint takes no request_id, so it is not retried.
    return client.post(
        "/api/v1/simulation/deposit/create",
        {"global_account_id": account_id, "amount": amount, "payer_name": payer, "reference": reference},
        attempts=1,
    )
