"""Human approval, bound to the exact terms the approver saw."""

import hashlib
import json
from dataclasses import asdict, dataclass

from leash.policy import Quote


@dataclass(frozen=True)
class Approval:
    digest: str
    approver: str


def terms_digest(vendor: str, quote: Quote) -> str:
    terms = {"vendor": vendor, **asdict(quote)}
    return hashlib.sha256(json.dumps(terms, sort_keys=True).encode()).hexdigest()


def covers(approval: Approval | None, vendor: str, quote: Quote) -> bool:
    """An approval only authorizes the terms it was given; any change needs a new one."""
    return approval is not None and approval.digest == terms_digest(vendor, quote)
