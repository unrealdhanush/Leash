"""Sandbox probe: can a single-use card be unfrozen after its one charge? Compares SINGLE and MULTIPLE."""
import os
import sys

sys.path.insert(0, "/app")
from leash import cards  # noqa: E402
from leash.client import AirwallexClient, new_request_id  # noqa: E402
from leash.policy import Quote, card_controls  # noqa: E402
from leash.sandbox import CardSimulator  # noqa: E402

client = AirwallexClient.from_env()
sim = CardSimulator(client)
email = os.environ["LEASH_CARDHOLDER_EMAIL"].strip('"')
by = os.environ["LEASH_CREATED_BY"].strip('"')
holder = cards.get_or_create_cardholder(client, email)
quote = Quote("annual", 4200.0, 1, "USD", "5734")


def issue(count):
    controls = card_controls(quote) | {"allowed_transaction_count": count}
    card = client.post("/api/v1/issuing/cards/create", {
        "cardholder_id": holder, "created_by": by, "form_factor": "VIRTUAL", "is_personalized": False,
        "program": {"purpose": "COMMERCIAL"}, "purpose": "SUBSCRIPTIONS", "nick_name": f"probe {count}",
        "authorization_controls": controls}, request_id=new_request_id())
    return card["card_id"]


def status(card_id):
    return client.get(f"/api/v1/issuing/cards/{card_id}")["card_status"]


def attempt(label, fn):
    try:
        print("   ", label, "->", fn())
    except Exception as exc:
        print("   ", label, "-> ERROR", exc)


for count, charge_first in (("SINGLE", False), ("SINGLE", True), ("MULTIPLE", True)):
    card = issue(count)
    print(count, "charge first" if charge_first else "no charge", card)
    if charge_first:
        r = sim.authorize(card, 4200.0, "USD", "5734")
        print("    charge", r.accepted, r.failure_reason, "| status now", status(card))
    attempt("freeze", lambda: cards.set_frozen(client, card, True))
    attempt("unfreeze", lambda: cards.set_frozen(client, card, False))
    r = sim.authorize(card, 4200.0, "USD", "5734")
    print("    second charge", r.accepted, r.failure_reason, "| status", status(card))
