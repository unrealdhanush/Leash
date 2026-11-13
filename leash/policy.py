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

    def charge_weeks(self, horizon: int) -> list[int]:
        """Weeks (1-based) in which this quote charges the card, first charge in week 1."""
        every = 52 // self.charges_per_year
        return list(range(1, horizon + 1, every))


@dataclass(frozen=True)
class CashFlow:
    week: int
    amount: float  # positive in, negative out
    label: str


@dataclass(frozen=True)
class Policy:
    auto_approve_max: float  # largest single charge the agent may make without a human
    reserve_floor: float  # cash must never drop below this in any forecast week
    horizon_weeks: int = 12
    currency: str = "USD"


def forecast(cash_now: float, plan: list[CashFlow], quote: Quote, horizon: int) -> list[float]:
    """Week-end balances for weeks 1..horizon, including this quote's charges."""
    charges = set(quote.charge_weeks(horizon))
    balances, balance = [], cash_now
    for week in range(1, horizon + 1):
        balance += sum(f.amount for f in plan if f.week == week)
        if week in charges:
            balance -= quote.charge
        balances.append(round(balance, 2))
    return balances


@dataclass(frozen=True)
class Assessment:
    quote: Quote
    balances: list[float]
    within_auto_approve: bool
    breach_week: int | None  # first week below the reserve floor

    @property
    def allowed(self) -> bool:
        return self.within_auto_approve and self.breach_week is None

    @property
    def low_point(self) -> float:
        return min(self.balances)

    @property
    def reasons(self) -> list[str]:
        out = []
        if not self.within_auto_approve:
            out.append("charge exceeds auto-approve limit; needs human approval")
        if self.breach_week is not None:
            out.append(f"cash drops below the reserve in week {self.breach_week}")
        return out


@dataclass(frozen=True)
class Decision:
    chosen: Quote | None
    assessments: list[Assessment]


def assess(quote: Quote, cash_now: float, plan: list[CashFlow], policy: Policy) -> Assessment:
    balances = forecast(cash_now, plan, quote, policy.horizon_weeks)
    breach = next((w for w, b in enumerate(balances, start=1) if b < policy.reserve_floor), None)
    return Assessment(
        quote=quote,
        balances=balances,
        within_auto_approve=quote.currency == policy.currency and quote.charge <= policy.auto_approve_max,
        breach_week=breach,
    )


def decide(quotes: list[Quote], cash_now: float, plan: list[CashFlow], policy: Policy) -> Decision:
    """Pick the cheapest-per-year quote that passes every policy check."""
    assessments = [assess(q, cash_now, plan, policy) for q in quotes]
    allowed = [a.quote for a in assessments if a.allowed]
    chosen = min(allowed, key=lambda q: q.annual_cost) if allowed else None
    return Decision(chosen=chosen, assessments=assessments)


def card_controls(quote: Quote) -> dict:
    """Card authorization_controls that allow one charge per billing period, at this vendor's MCC and currency only."""
    return {
        "allowed_transaction_count": "MULTIPLE" if quote.charges_per_year > 1 else "SINGLE",
        "allowed_currencies": [quote.currency],
        "allowed_merchant_categories": [quote.merchant_category],
        "transaction_limits": card_limits(quote),
    }


def card_limits(quote: Quote) -> dict:
    interval = "MONTHLY" if quote.charges_per_year == 12 else "ALL_TIME"
    return {
        "currency": quote.currency,
        "limits": [
            {"amount": quote.charge, "interval": "PER_TRANSACTION"},
            {"amount": quote.charge, "interval": interval},
        ],
    }
