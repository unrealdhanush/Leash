# Leash

An AI purchase agent that cannot overspend, because its limits live in the card, not the prompt.

The agent reads a vendor's quote and explains its reasoning. Everything that matters for money happens elsewhere: plain Python decides against live Airwallex cash and a written policy, and an Airwallex virtual card enforces that decision. If the agent is wrong, confused or manipulated, Airwallex declines the charge.

Built for the Airwallex Agentic Banking Hackathon (Track 2: Intent-Bound Purchase Agent). Airwallex sandbox only.

## The demo

`main.py` runs seven scenes against the live sandbox:

| Scene | What happens | Airwallex |
|---|---|---|
| Setup | USD cash is set to 80,000 so the forecast has a startup-sized balance (the sandbox starts with millions) | FX conversions |
| 1. Read and decide | Claude reads a vendor email and extracts the billing options; code checks each price appears verbatim in the email. A 12-week cash forecast shows annual billing dropping below the 25,000 reserve in week 8, so the agent picks monthly and Claude explains why | Balances |
| 2. Escalate | The cheaper annual plan goes to a human, bound to its exact terms | |
| 3. Issue the card | Virtual card: 1,000 per charge and per month, USD only, software merchants (MCC 5734) only | Cardholders, cards |
| 4. Declines | Over the limit, wrong currency and a restaurant charge are each declined with their own reason | Issuing simulations |
| 5. Price rise | The vendor emails a new price and bills it: declined. The agent re-reads, re-checks policy and asks for approval bound to the new terms, then raises the card limit; the retry clears at exactly the new limit | Card update |
| 6. Late invoice | A 60,000 customer invoice slips three weeks; the forecast now breaks the reserve, so the agent freezes the card and the next charge is declined | Card update (freeze) |
| 7. Deposit lands | The invoice is paid into the global account; the forecast recovers and the agent unfreezes the card | Deposit simulation, limits |

## Setup

1. Install [uv](https://docs.astral.sh/uv/).
2. Create `.env` in the repo root (it is gitignored):

   ```
   AIRWALLEX_CLIENT_ID=...
   AIRWALLEX_API_KEY=...
   ANTHROPIC_API_KEY=...
   LEASH_CARDHOLDER_EMAIL=you@example.com
   LEASH_CREATED_BY="Your Full Name"
   ```

   Get the Airwallex client ID and API key from the sandbox web app under Developer > API keys.

3. Run:

   ```
   uv run --env-file .env main.py           # asks you to approve or decline at each approval
   uv run --env-file .env main.py --auto    # declines the annual plan, approves the price change
   uv run --env-file .env main.py --json    # same as --auto, printing one JSON event per line
   ```

Each run issues a new card and moves sandbox money: the setup step converts USD to or from EUR so every run starts at 80,000 USD.

## Code

| File | Role |
|---|---|
| `leash/agent.py` | Claude (`claude-opus-5-5`): reads quotes into structured options and explains decisions. It never decides |
| `leash/policy.py` | Quotes, the cash forecast, policy checks, and the card controls a decision maps to |
| `leash/approval.py` | Approvals as a hash of vendor and terms; any change to the terms needs a new approval |
| `leash/cards.py` | Cardholder, card issuing, limit updates, freeze and unfreeze |
| `leash/treasury.py` | Balances, demo cash setup, global account deposits |
| `leash/sandbox.py` | Card transaction simulations, behind one interface so they can be swapped out |
| `leash/client.py` | Airwallex REST client: token caching, one `request_id` per create reused on retries |
| `leash/demo.py` | The scenes. Emits events and asks for approvals through callbacks, so a UI can drive the same flow |
| `main.py` | Terminal renderer and JSON event stream |

## Sandbox notes

- Amounts are major units: `1000` is one thousand dollars.
- REST simulations return a card transaction event: read `process_result` (`APPROVED` or `DECLINED`) and `failure_reason`. The MCP tool returns an older shape (`transaction_type`, `status`), where a decline still says `CLEARING` and only `status: FAILED` marks it.
- Simulated charges default to MCC 7531 (auto repair). On a card with a merchant-category allowlist, pass `merchant_category_code` or every charge is declined.
- The cardholder type field is `type` on REST and `cardholder_type` on the MCP server.
- Card simulations, deposit simulations and card updates take no `request_id`; simulations are not retried.
- A single FX conversion above 1,000,000 is rejected with `amount_above_limit`.
