# Leash

A purchase agent that cannot overspend: it compares quotes against live cash and a policy written in code, then issues an Airwallex virtual card whose limits match the decision. Sandbox only.

## Setup

1. Install [uv](https://docs.astral.sh/uv/).
2. Create `.env` in the repo root (it is gitignored):

   ```
   AIRWALLEX_CLIENT_ID=...
   AIRWALLEX_API_KEY=...
   LEASH_CARDHOLDER_EMAIL=you@example.com
   LEASH_CREATED_BY="Your Full Name"
   ```

   Get the client ID and API key from the Airwallex sandbox web app under Developer > API keys.

3. Run:

   ```
   uv run --env-file .env main.py
   ```

## What a run does

1. Reads available USD cash from `GET /api/v1/balances/current`.
2. Checks each quote against the policy in `leash/policy.py` (auto-approve limit, cash reserve floor) and picks the cheapest one that passes.
3. Finds or creates a DELEGATE cardholder, then issues a virtual card limited to one charge of the chosen amount per billing period, in the quote's currency and at the vendor's merchant category (MCC 5734, software) only.
4. Simulates four charges and checks each outcome:

   | Charge | Expected |
   |---|---|
   | 0.01 over the limit | declined, `LIMIT_EXCEEDED` |
   | 10.00 EUR | declined, `CURRENCY_NOT_ALLOWED` |
   | 10.00 USD at a restaurant (MCC 5812) | declined, `MERCHANT_CATEGORY_NOT_ALLOWED` |
   | exactly at the limit | cleared (limits are inclusive) |
5. Prints the card's remaining limits.

Each run issues a new card with a fresh `request_id`. Retries of the same create reuse its `request_id`.

## Sandbox notes

- Amounts are major units: `1000` is one thousand dollars.
- REST simulations return a card transaction event: read `process_result` (`APPROVED` or `DECLINED`) and `failure_reason`. The MCP tool returns an older shape (`transaction_type`, `status`), where a decline still says `CLEARING` and only `status: FAILED` marks it.
- The cardholder type field is `type` on REST and `cardholder_type` on the MCP server.
- The simulation endpoint takes no `request_id`, so simulated charges are not retried.
- Simulated charges default to MCC 7531 (auto repair). On a card with a merchant-category allowlist, pass `merchant_category_code` or every charge is declined.
