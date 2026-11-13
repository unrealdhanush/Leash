// Plain-language chapter for each scene the agent emits. Keys match the scene number in the event stream.
export const CHAPTERS = [
  {
    key: "setup", n: "0", short: "Open the books", title: "Open the books",
    why: "The sandbox balance is set to a known figure so the cash forecast has something real to start from.",
    say: "This is a startup with 80,000 dollars in its Airwallex account. Leash sets that balance in the sandbox so every purchase starts from the same books.",
  },
  {
    key: "1", n: "1", short: "Read the quote", title: "Read the quote and pick a plan",
    why: "The agent pulls each way to pay out of the vendor's email. Policy code checks every option against live cash and the 12-week forecast, then picks one.",
    say: "A vendor emailed a quote. Claude only reads it, and every price it pulls out has to appear word for word in the email. The choice is made by policy code against the live Airwallex balance and a 12-week cash forecast.",
  },
  {
    key: "2", n: "2", short: "Ask a person", title: "Bring the cheaper option to a person",
    why: "A cheaper option broke policy. Leash does not drop it quietly: it shows you the saving and the reason, and waits for your answer.",
    say: "The cheaper option broke policy, so the agent neither takes it nor hides it. It asks me, with the saving and the reason, and my answer is bound to these exact terms.",
  },
  {
    key: "3", n: "3", short: "Issue the card", title: "Issue a card for exactly this",
    why: "A virtual card is created for this vendor, capped at the decided amount, in one currency, for one type of merchant.",
    say: "Now the decision becomes a real Airwallex virtual card: this amount, this currency, this kind of merchant. The limit lives in the card, not in a prompt.",
  },
  {
    key: "4", n: "4", short: "Try to overspend", title: "Try to overspend",
    why: "Three charges the decision does not cover are sent to the card: too much, the wrong currency, the wrong kind of merchant. Airwallex should decline all three.",
    say: "Suppose the agent is wrong or has been manipulated. One cent over, the wrong currency, a restaurant: Airwallex declines each one and says why.",
  },
  {
    key: "5", n: "5", short: "Price goes up", title: "The vendor raises the price",
    why: "The new price is billed and the card declines it. The limit only moves after a person approves the new terms.",
    say: "The vendor raises the price and bills it. The card declines. The agent re-reads the email, re-checks policy and asks me again, because my earlier yes covered the old terms only.",
  },
  {
    key: "6", n: "6", short: "Pay at checkout", title: "Pay at checkout",
    why: "The merchant checks who is asking before it takes the card. Only our agent's signed intent to pay goes through, and only once.",
    say: "At checkout the merchant asks who the agent is, using Visa Trusted Agent Protocol signatures. Unsigned, unknown, browse-only and replayed requests are rejected; one signed intent to pay is charged. The merchant and key directory here are local stand-ins.",
  },
  {
    key: "7", n: "7", short: "A customer pays late", title: "A customer pays late",
    why: "A customer invoice slips by three weeks. If the forecast now falls under the cash reserve, the card is frozen before the vendor can bill it.",
    say: "The financial context changes: a customer invoice slips three weeks. If the forecast now breaks the reserve, the agent freezes the card and the vendor's next charge is declined.",
  },
  {
    key: "8", n: "8", short: "The money arrives", title: "The money arrives",
    why: "The deposit lands, the forecast is checked again, and the card is unfrozen if cash clears the reserve.",
    say: "The deposit lands in the Airwallex account and the forecast is checked again. If it clears the reserve the card is unfrozen. This is the final state: the card, its status and what is left on its limits.",
  },
];

export const chapterFor = (key) => CHAPTERS.find((c) => c.key === key);
