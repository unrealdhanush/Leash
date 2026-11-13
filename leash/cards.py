"""Issuing: the cardholder, the agent's card, and the controls the agent may change."""

from leash.client import AirwallexClient, new_request_id
from leash.policy import Quote, card_controls, card_limits


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


def issue_card(client: AirwallexClient, cardholder_id: str, vendor: str, quote: Quote, created_by: str) -> str:
    card = client.post(
        "/api/v1/issuing/cards/create",
        {
            "cardholder_id": cardholder_id,
            "created_by": created_by,
            "form_factor": "VIRTUAL",
            "is_personalized": False,
            "program": {"purpose": "COMMERCIAL"},
            "purpose": "SUBSCRIPTIONS",
            "nick_name": f"Leash {vendor} {quote.name}"[:50],
            "authorization_controls": card_controls(quote),
            "metadata": {"vendor": vendor[:150], "decision": quote.name, "charge": f"{quote.charge} {quote.currency}"},
        },
        request_id=new_request_id(),
    )
    return card["card_id"]


# Updates set state rather than create anything, so the endpoint takes no request_id and retrying is safe.

def update_limits(client: AirwallexClient, card_id: str, quote: Quote) -> dict:
    return client.post(f"/api/v1/issuing/cards/{card_id}/update", {"authorization_controls": {"transaction_limits": card_limits(quote)}})


def set_frozen(client: AirwallexClient, card_id: str, frozen: bool) -> str:
    card = client.post(f"/api/v1/issuing/cards/{card_id}/update", {"card_status": "INACTIVE" if frozen else "ACTIVE"})
    return card["card_status"]


def remaining_limits(client: AirwallexClient, card_id: str) -> dict:
    return client.get(f"/api/v1/issuing/cards/{card_id}/limits")
