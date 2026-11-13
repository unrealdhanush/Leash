"""Leash purchase agent demo. Run: uv run --env-file .env main.py [--auto] [--json]"""

import argparse
import json
import os

from leash.agent import Agent
from leash.client import AirwallexClient
from leash.demo import Config, Demo

AUTO_ANSWERS = [False, True]  # decline the cheaper out-of-policy plan, approve the price change

BOLD, DIM, RED, GREEN, YELLOW, RESET = "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[0m"


def render(kind: str, **e) -> None:
    if kind == "scene":
        print(f"\n{BOLD}━━ {e['title']}{RESET}")
    elif kind == "info":
        print(f"  {e['text']}")
    elif kind == "quote_text":
        print(f"{DIM}" + "\n".join(f"  │ {line}" for line in e["text"].strip().splitlines()) + RESET)
    elif kind == "quotes_read":
        print(f"  Agent read {len(e['quotes'])} options from {e['vendor']}:")
        for q in e["quotes"]:
            print(f"    {q['name']:8} {q['charge']:>10,.2f} {q['currency']} x{q['charges_per_year']:<2} = {q['annual_cost']:,.2f}/yr")
    elif kind == "cash":
        print(f"  Live {e['currency']} cash: {e['available']:,.2f}   reserve floor: {e['reserve_floor']:,.2f}")
    elif kind == "assessments":
        for a in e["items"]:
            q = a["quote"]
            verdict = f"{GREEN}within policy{RESET}" if a["allowed"] else f"{RED}{'; '.join(a['reasons'])}{RESET}"
            print(f"    {q['name']:8} {q['charge']:>10,.2f}  low point {a['low_point']:>10,.2f}  {verdict}")
    elif kind == "decision":
        print(f"  {BOLD}Decision: {e['chosen']}{RESET}")
        print(f"  {DIM}Agent:{RESET} {e['explanation']}")
    elif kind == "approval_request":
        q = e["quote"]
        print(f"  {YELLOW}┌ APPROVAL NEEDED{RESET}")
        print(f"  {YELLOW}│{RESET} vendor    {e['vendor']}")
        print(f"  {YELLOW}│{RESET} terms     {q['charge']:,.2f} {q['currency']} x{q['charges_per_year']} per year ({q['name']})")
        for reason in e["reasons"]:
            print(f"  {YELLOW}│{RESET} why       {reason}")
        print(f"  {YELLOW}│{RESET} binds to  {e['digest'][:12]}")
    elif kind == "approval_result":
        print(f"  {YELLOW}└{RESET} {e['approver']}: {'approved' if e['approved'] else 'declined'}")
    elif kind == "card_issued":
        q = e["quote"]
        print(f"  Virtual card {e['card_id']}")
        print(f"    limit {q['charge']:,.2f} per charge and per period · {q['currency']} only · MCC {q['merchant_category']} only")
    elif kind == "card_updated":
        print(f"  Card limit raised to {e['quote']['charge']:,.2f} under approval {e['approval']}")
    elif kind == "card_status":
        color = RED if e["status"] == "INACTIVE" else GREEN
        print(f"  Card {color}{e['status']}{RESET}: {e['reason']}")
    elif kind == "charge":
        outcome = f"{GREEN}cleared{RESET}" if e["accepted"] else f"{RED}declined {e['failure_reason']}{RESET}"
        check = "" if e["as_expected"] else f"  {RED}UNEXPECTED{RESET}"
        print(f"    {e['label']:32} {e['amount']:>10,.2f} {e['currency']} MCC {e['merchant_category']}  {outcome}{check}")
    elif kind == "checkout":
        if not e["verified"]:
            outcome = f"{RED}rejected by merchant: {e['rejection']}{RESET}"
        elif e["accepted"]:
            outcome = f"{GREEN}verified · card charged{RESET}"
        else:
            outcome = f"{RED}verified · card declined {e['failure_reason']}{RESET}"
        check = "" if e["as_expected"] else f"  {RED}UNEXPECTED{RESET}"
        print(f"    {e['label']:34} {e['amount']:>10,.2f} {e['currency']}  {outcome}{check}")
    elif kind == "deposit":
        print(f"  Deposit from {e['payer']}: {e['amount']:,.2f} {e['currency']} ({e['status']})")
    elif kind == "limits":
        for limit in e["limits"]:
            print(f"    {limit['interval']:15} {limit['remaining']:>10,.2f} left of {limit['amount']:,.2f} {e['currency']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="answer approvals automatically: decline the cheaper plan, approve the price change")
    parser.add_argument("--json", action="store_true", help="print events as JSON lines (implies --auto)")
    args = parser.parse_args()

    email = os.environ.get("LEASH_CARDHOLDER_EMAIL")
    created_by = os.environ.get("LEASH_CREATED_BY")
    if not email or not created_by:
        raise SystemExit("Set LEASH_CARDHOLDER_EMAIL and LEASH_CREATED_BY in .env")
    config = Config(cardholder_email=email, created_by=created_by, approver=created_by)

    answers = iter(AUTO_ANSWERS)
    if args.json:
        emit = lambda kind, **e: print(json.dumps({"event": kind, **e}), flush=True)  # noqa: E731
    else:
        emit = render
    if args.auto or args.json:
        ask = lambda request: next(answers, False)  # noqa: E731
    else:
        ask = lambda request: input(f"  {YELLOW}│{RESET} approve? [y/N] ").strip().lower() == "y"  # noqa: E731

    Demo(AirwallexClient.from_env(), Agent(), config, emit, ask).run()


if __name__ == "__main__":
    main()
