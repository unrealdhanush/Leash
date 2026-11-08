"""Sandbox-only simulation calls, kept behind one interface so they can be swapped out."""

from dataclasses import dataclass

from leash.client import AirwallexClient


@dataclass(frozen=True)
class AuthResult:
    transaction_id: str
    amount: float
    currency: str
    process_result: str  # APPROVED or DECLINED
    failure_reason: str | None

    @property
    def accepted(self) -> bool:
        return self.process_result == "APPROVED"


class CardSimulator:
    def __init__(self, client: AirwallexClient):
        self._client = client

    def authorize(self, card_id: str, amount: float, currency: str, mcc: str | None = None) -> AuthResult:
        # The simulation endpoint takes no request_id, so it is not retried.
        body = {
            "card_id": card_id,
            "transaction_amount": amount,
            "transaction_currency": currency,
            "single_phase": True,
        }
        if mcc:
            body["merchant_category_code"] = mcc
        tx = self._client.post("/api/v1/simulation/issuing/create", body, attempts=1)
        return AuthResult(
            transaction_id=tx["card_transaction_id"],
            amount=tx["transaction_amount"],
            currency=tx["transaction_currency"],
            process_result=tx["process_result"],
            failure_reason=tx.get("failure_reason"),
        )
