"""The Leash demo as a sequence of scenes. It emits events and asks for approvals through callbacks,
so a terminal, a web UI or a test can drive the same flow."""

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from leash import cards, treasury
from leash.agent import Agent
from leash.approval import Approval, covers, terms_digest
from leash.client import AirwallexClient
from leash.merchant import MockMerchant, place_order, sign_checkout
from leash.policy import Assessment, CashFlow, Policy, Quote, assess, decide
from leash.sandbox import CardSimulator
from leash.tap import BROWSE, AgentIdentity, KeyDirectory, Verifier

QUOTES_DIR = Path(__file__).resolve().parent.parent / "quotes"
SAAS_MCC = "5734"  # Computer Software Stores
POLICY = Policy(auto_approve_max=5000.00, reserve_floor=25000.00, horizon_weeks=12)
OPERATING_CASH = 80000.00
INVOICE = CashFlow(week=9, amount=60000.00, label="Acme Corp invoice")
CASH_PLAN = (
    [CashFlow(week=w, amount=4000.00, label="subscription revenue") for w in range(1, 13)]
    + [CashFlow(week=w, amount=-20000.00, label="payroll") for w in range(2, 13, 2)]
    + [INVOICE]
)

Emit = Callable[..., None]
Ask = Callable[[dict], bool]


@dataclass
class Config:
    cardholder_email: str
    created_by: str
    approver: str


class Demo:
    def __init__(self, client: AirwallexClient, agent: Agent, config: Config, emit: Emit, ask: Ask):
        self.client = client
        self.agent = agent
        self.config = config
        self.emit = emit
        self.ask = ask
        self.sim = CardSimulator(client)
        self.vendor = ""
        self.quote: Quote | None = None
        self.card_id = ""

    def run(self) -> None:
        self.setup()
        options = self.read_and_decide()
        self.escalate_cheaper_option(options)
        self.issue_card()
        self.vendor_charges()
        self.price_increase()
        self.checkout()
        self.invoice_slips()
        self.deposit_lands()

    # Scenes

    def setup(self) -> None:
        self.emit("scene", title="Setup")
        treasury.set_operating_cash(self.client, POLICY.currency, OPERATING_CASH)
        self.emit("info", text=f"Sandbox USD set to {OPERATING_CASH:,.2f} so the forecast has a startup-sized balance.")

    def read_and_decide(self) -> list[Assessment]:
        self.emit("scene", title="1. Read the quote and decide")
        text = (QUOTES_DIR / "northwind.txt").read_text()
        self.emit("quote_text", text=text)
        self.vendor, quotes = self.agent.read_quote(text, SAAS_MCC)
        self.emit("quotes_read", vendor=self.vendor, quotes=[_quote(q) for q in quotes])

        cash = treasury.cash_available(self.client, POLICY.currency)
        decision = decide(quotes, cash, CASH_PLAN, POLICY)
        self.emit("cash", currency=POLICY.currency, available=cash, reserve_floor=POLICY.reserve_floor, plan=[_flow(f) for f in CASH_PLAN])
        self.emit("assessments", items=[_assessment(a) for a in decision.assessments])
        if decision.chosen is None:
            raise SystemExit("No quote passes policy; escalate to a human.")
        self.quote = decision.chosen
        facts = {
            "vendor": self.vendor,
            "cash_now": cash,
            "policy": {"auto_approve_max": POLICY.auto_approve_max, "reserve_floor": POLICY.reserve_floor, "horizon_weeks": POLICY.horizon_weeks},
            "options": [_assessment(a) for a in decision.assessments],
            "chosen": self.quote.name,
        }
        self.emit("decision", chosen=self.quote.name, explanation=self.agent.explain(facts))
        return decision.assessments

    def escalate_cheaper_option(self, options: list[Assessment]) -> None:
        """A cheaper option that broke policy goes to a human rather than being dropped silently."""
        cheaper = [a for a in options if not a.allowed and a.quote.annual_cost < self.quote.annual_cost]
        if not cheaper:
            return
        self.emit("scene", title="2. Escalate the cheaper option")
        option = cheaper[0]
        saving = self.quote.annual_cost - option.quote.annual_cost
        approval = self._approve(option.quote, [f"saves {saving:,.2f} {option.quote.currency} a year", *option.reasons])
        if approval:
            self.quote = option.quote
            self.emit("info", text=f"Approved by {approval.approver}: switching to {option.quote.name}.")
        else:
            self.emit("info", text=f"Declined: staying with {self.quote.name}.")

    def issue_card(self) -> None:
        self.emit("scene", title="3. Issue a card that matches the decision")
        cardholder = cards.get_or_create_cardholder(self.client, self.config.cardholder_email)
        self.card_id = cards.issue_card(self.client, cardholder, self.vendor, self.quote, self.config.created_by)
        self.emit("card_issued", card_id=self.card_id, quote=_quote(self.quote))

    def vendor_charges(self) -> None:
        self.emit("scene", title="4. Charges outside the decision are declined by Airwallex")
        q = self.quote
        self._charge("over the limit", round(q.charge + 0.01, 2), q.currency, q.merchant_category, "LIMIT_EXCEEDED")
        self._charge("wrong currency", 10.00, "EUR", q.merchant_category, "CURRENCY_NOT_ALLOWED")
        self._charge("wrong merchant (restaurant)", 10.00, q.currency, "5812", "MERCHANT_CATEGORY_NOT_ALLOWED")

    def price_increase(self) -> None:
        self.emit("scene", title="5. The vendor raises its price")
        text = (QUOTES_DIR / "northwind_increase.txt").read_text()
        self.emit("quote_text", text=text)
        _, quotes = self.agent.read_quote(text, SAAS_MCC)
        new = next((q for q in quotes if q.charges_per_year == self.quote.charges_per_year), None)
        if new is None or new.charge == self.quote.charge:
            self.emit("info", text="No change to our plan's price.")
            return

        self._charge("vendor bills the new price", new.charge, new.currency, new.merchant_category, "LIMIT_EXCEEDED")
        cash = treasury.cash_available(self.client, POLICY.currency)
        check = assess(new, cash, CASH_PLAN, POLICY)
        self.emit("assessments", items=[_assessment(check)])
        if not check.allowed:
            self.emit("info", text="The new price breaks policy; the card stays as it is.")
            return
        approval = self._approve(new, [f"price changed from {self.quote.charge:,.2f} to {new.charge:,.2f}"])
        if not covers(approval, self.vendor, new):
            self.emit("info", text="Not approved; the card keeps the old limit.")
            return
        cards.update_limits(self.client, self.card_id, new)
        self.quote = new
        self.emit("card_updated", card_id=self.card_id, quote=_quote(new), approval=approval.digest[:12])

    def checkout(self) -> None:
        """The merchant asks who the agent is (Visa TAP); the card still decides what it may spend."""
        self.emit("scene", title="6. Checkout: the merchant verifies the agent (Visa Trusted Agent Protocol)")
        identity, directory = AgentIdentity(), KeyDirectory()
        directory.register(identity)
        self.emit("info", text=f"Agent key {identity.keyid} (Ed25519) registered in the key directory.")
        order = {"card_id": self.card_id, "amount": self.quote.charge, "currency": self.quote.currency}
        with MockMerchant(Verifier(directory), self.sim, self.quote.merchant_category) as shop:
            signed = sign_checkout(identity, shop.authority)
            self._order(shop, "unsigned request", {}, order, expect_ok=False)
            self._order(shop, "rogue agent (unknown key)", sign_checkout(AgentIdentity(), shop.authority), order, expect_ok=False)
            self._order(shop, "our agent, browsing intent only", sign_checkout(identity, shop.authority, BROWSE), order, expect_ok=False)
            self._order(shop, "our agent, signed intent to pay", signed, order, expect_ok=True)
            self._order(shop, "replay of that exact request", signed, order, expect_ok=False)

    def invoice_slips(self) -> None:
        self.emit("scene", title="7. A customer invoice will land late")
        late = replace(INVOICE, week=12)
        plan = [late if f is INVOICE else f for f in CASH_PLAN]
        self.emit("info", text=f"{INVOICE.label} moves from week {INVOICE.week} to week {late.week}.")
        cash = treasury.cash_available(self.client, POLICY.currency)
        check = assess(self.quote, cash, plan, POLICY)
        self.emit("assessments", items=[_assessment(check)])
        if check.allowed:
            self.emit("info", text="Still within policy; no change.")
            return
        status = cards.set_frozen(self.client, self.card_id, True)
        self.emit("card_status", card_id=self.card_id, status=status, reason=check.reasons[0])
        self._charge("vendor bills while frozen", self.quote.charge, self.quote.currency, self.quote.merchant_category, "any")

    def deposit_lands(self) -> None:
        self.emit("scene", title="8. The deposit lands")
        account = treasury.global_account_id(self.client, POLICY.currency)
        before = treasury.cash_available(self.client, POLICY.currency)
        deposit = treasury.simulate_deposit(self.client, account, INVOICE.amount, "Acme Corp", "INV-2041")
        self.emit("deposit", amount=deposit.get("amount", INVOICE.amount), currency=POLICY.currency, payer="Acme Corp", status=deposit.get("status"))
        plan = [f for f in CASH_PLAN if f is not INVOICE]
        cash = treasury.cash_available(self.client, POLICY.currency)
        for _ in range(15):  # the sandbox can take a few seconds to show the deposit in the balance
            if cash > before:
                break
            time.sleep(1)
            cash = treasury.cash_available(self.client, POLICY.currency)
        self.emit("cash", currency=POLICY.currency, available=cash, reserve_floor=POLICY.reserve_floor, plan=[_flow(f) for f in plan])
        check = assess(self.quote, cash, plan, POLICY)
        self.emit("assessments", items=[_assessment(check)])
        if check.allowed:
            status = cards.set_frozen(self.client, self.card_id, False)
            self.emit("card_status", card_id=self.card_id, status=status, reason="cash forecast back within policy")
        self.emit("limits", card_id=self.card_id, **cards.remaining_limits(self.client, self.card_id))

    # Helpers

    def _approve(self, quote: Quote, reasons: list[str]) -> Approval | None:
        request = {"vendor": self.vendor, "quote": _quote(quote), "reasons": reasons, "digest": terms_digest(self.vendor, quote)}
        self.emit("approval_request", **request)
        approved = self.ask(request)
        self.emit("approval_result", approved=approved, approver=self.config.approver)
        return Approval(digest=request["digest"], approver=self.config.approver) if approved else None

    def _order(self, shop: MockMerchant, label: str, headers: dict, order: dict, expect_ok: bool) -> None:
        status, body = place_order(shop.authority, headers, order)
        verified = status == 200
        self.emit(
            "checkout",
            label=label,
            amount=order["amount"],
            currency=order["currency"],
            verified=verified,
            rejection=body.get("error"),
            accepted=body.get("accepted", False),
            failure_reason=body.get("failure_reason"),
            as_expected=verified == expect_ok and (not verified or body.get("accepted", False)),
        )

    def _charge(self, label: str, amount: float, currency: str, mcc: str, expected_failure: str | None) -> None:
        result = self.sim.authorize(self.card_id, amount, currency, mcc)
        as_expected = (
            not result.accepted if expected_failure == "any" else result.failure_reason == expected_failure
        )
        self.emit(
            "charge",
            label=label,
            amount=amount,
            currency=currency,
            merchant_category=mcc,
            accepted=result.accepted,
            failure_reason=result.failure_reason,
            as_expected=as_expected,
        )


def _quote(q: Quote) -> dict:
    return {"name": q.name, "charge": q.charge, "charges_per_year": q.charges_per_year, "currency": q.currency,
            "merchant_category": q.merchant_category, "annual_cost": q.annual_cost}


def _flow(f: CashFlow) -> dict:
    return {"week": f.week, "amount": f.amount, "label": f.label}


def _assessment(a: Assessment) -> dict:
    return {"quote": _quote(a.quote), "allowed": a.allowed, "reasons": a.reasons, "breach_week": a.breach_week,
            "low_point": a.low_point, "balances": a.balances}
