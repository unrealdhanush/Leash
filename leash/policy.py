"""Purchase policy. Every decision is made here, in code, never in a prompt."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Quote:
    name: str
    charge: float  # amount of each charge, major units
    charges_per_year: int
    currency: str
    merchant_category: str  # vendor's Visa MCC

    @property
    def annual_cost(self) -> float:
        return round(self.charge * self.charges_per_year, 2)


@dataclass(frozen=True)
class Policy:
    auto_approve_max: float  # largest single charge the agent may make without a human
    reserve_floor: float  # cash that must remain after the first charge
    currency: str = "USD"


@dataclass(frozen=True)
class Assessment:
    quote: Quote
    within_auto_approve: bool
    keeps_reserve: bool

    @property
    def allowed(self) -> bool:
        return self.within_auto_approve and self.keeps_reserve

    @property
    def reasons(self) -> list[str]:
        out = []
        if not self.within_auto_approve:
            out.append("charge exceeds auto-approve limit; needs human approval")
        if not self.keeps_reserve:
            out.append("charge would push cash below the reserve floor")
        return out


@dataclass(frozen=True)
class Decision:
    chosen: Quote | None
    assessments: list[Assessment]


def decide(quotes: list[Quote], cash_available: float, policy: Policy) -> Decision:
    """Pick the cheapest-per-year quote that passes every policy check."""
    assessments = [
        Assessment(
            quote=q,
            within_auto_approve=q.currency == policy.currency and q.charge <= policy.auto_approve_max,
            keeps_reserve=cash_available - q.charge >= policy.reserve_floor,
        )
        for q in quotes
    ]
    allowed = [a.quote for a in assessments if a.allowed]
    chosen = min(allowed, key=lambda q: q.annual_cost) if allowed else None
    return Decision(chosen=chosen, assessments=assessments)


def card_controls(quote: Quote) -> dict:
    """Card authorization_controls that allow one charge per billing period, at this vendor's MCC and currency only."""
    interval = "MONTHLY" if quote.charges_per_year == 12 else "ALL_TIME"
    return {
        "allowed_transaction_count": "MULTIPLE" if quote.charges_per_year > 1 else "SINGLE",
        "allowed_currencies": [quote.currency],
        "allowed_merchant_categories": [quote.merchant_category],
        "transaction_limits": {
            "currency": quote.currency,
            "limits": [
                {"amount": quote.charge, "interval": "PER_TRANSACTION"},
                {"amount": quote.charge, "interval": interval},
            ],
        },
    }
