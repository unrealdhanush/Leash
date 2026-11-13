"""The model's two jobs: read a vendor quote, and explain a decision made in code. It decides nothing."""

import json
import re

import anthropic
from pydantic import BaseModel, Field

from leash.policy import Quote

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ExtractedOption(BaseModel):
    name: str = Field(description="Short billing option name, e.g. 'monthly' or 'annual'")
    amount_per_charge: float = Field(description="Amount of each charge in major units, before any optional add-ons")
    charges_per_year: int = Field(description="12 for monthly billing, 1 for annual up front")
    currency: str = Field(description="ISO 4217 code, e.g. USD")
    evidence: str = Field(description="The exact sentence from the quote that states this price, copied verbatim")


class ExtractedQuote(BaseModel):
    vendor: str
    options: list[ExtractedOption]


class ReadError(Exception):
    pass


class Agent:
    def __init__(self, client: anthropic.Anthropic | None = None):
        self._client = client or anthropic.Anthropic()

    def read_quote(self, text: str, merchant_category: str) -> tuple[str, list[Quote]]:
        """Extract billing options, then check every price against the source text."""
        response = self._client.beta.messages.parse(
            model=MODEL,
            max_tokens=4000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "low"},
            system=(
                "You extract billing options from vendor quotes for a finance team. "
                "List each way the customer can pay for the same plan. Ignore optional add-ons, taxes and other plans. "
                "Copy the evidence sentence exactly as written in the quote."
            ),
            messages=[{"role": "user", "content": text}],
            output_format=ExtractedQuote,
        )
        if response.stop_reason == "refusal":
            raise ReadError("model declined to read the quote")
        extracted = response.parsed_output

        quotes = []
        for option in extracted.options:
            _check_grounded(option, text)
            quotes.append(
                Quote(
                    name=option.name,
                    charge=round(option.amount_per_charge, 2),
                    charges_per_year=option.charges_per_year,
                    currency=option.currency.upper(),
                    merchant_category=merchant_category,
                )
            )
        if len(quotes) < 2:
            raise ReadError(f"expected at least two billing options, found {len(quotes)}")
        return extracted.vendor, quotes

    def explain(self, facts: dict) -> str:
        """Plain-English explanation of a decision the policy code already made."""
        response = self._client.beta.messages.create(
            model=MODEL,
            max_tokens=2000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            output_config={"effort": "low"},
            system=(
                "You explain a purchasing decision to a startup founder in 3 or 4 plain sentences. "
                "The decision was made by policy code; do not second-guess or change it. "
                "Use only the numbers in the facts you are given."
            ),
            messages=[{"role": "user", "content": json.dumps(facts, indent=2)}],
        )
        if response.stop_reason == "refusal":
            return "(explanation unavailable)"
        return "".join(b.text for b in response.content if b.type == "text").strip()


def _check_grounded(option: ExtractedOption, text: str) -> None:
    """The evidence must be in the quote, and the price must be in the evidence."""
    if _squash(option.evidence) not in _squash(text):
        raise ReadError(f"evidence for '{option.name}' is not in the quote: {option.evidence!r}")
    amounts = {float(m.replace(",", "")) for m in re.findall(r"\d[\d,]*(?:\.\d+)?", option.evidence)}
    if round(option.amount_per_charge, 2) not in amounts:
        raise ReadError(f"price {option.amount_per_charge} for '{option.name}' is not in its evidence")


def _squash(s: str) -> str:
    return " ".join(s.split()).lower()
