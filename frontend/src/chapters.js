// Plain-language chapter for each scene the agent emits. Keys match the scene number in the event stream.
export const CHAPTERS = [
  {
    key: "setup", n: "0", short: "Open the books", title: "Open the books",
    why: "The sandbox balance is set to a known figure so the cash forecast has something real to start from.",
  },
  {
    key: "1", n: "1", short: "Read the quote", title: "Read the quote and pick a plan",
    why: "The agent pulls each way to pay out of the vendor's email. Policy code checks every option against live cash and the 12-week forecast, then picks one.",
  },
  {
    key: "2", n: "2", short: "Ask a person", title: "Bring the cheaper option to a person",
    why: "A cheaper option broke policy. Leash does not drop it quietly: it shows you the saving and the reason, and waits for your answer.",
  },
  {
    key: "3", n: "3", short: "Issue the card", title: "Issue a card for exactly this",
    why: "A virtual card is created for this vendor, capped at the decided amount, in one currency, for one type of merchant.",
  },
  {
    key: "4", n: "4", short: "Try to overspend", title: "Try to overspend",
    why: "Three charges the decision does not cover are sent to the card: too much, the wrong currency, the wrong kind of merchant. Airwallex should decline all three.",
  },
  {
    key: "5", n: "5", short: "Price goes up", title: "The vendor raises the price",
    why: "The new price is billed and the card declines it. The limit only moves after a person approves the new terms.",
  },
  {
    key: "6", n: "6", short: "Pay at checkout", title: "Pay at checkout",
    why: "The merchant checks who is asking before it takes the card. Only our agent's signed intent to pay goes through, and only once.",
  },
  {
    key: "7", n: "7", short: "A customer pays late", title: "A customer pays late",
    why: "A customer invoice slips by three weeks. If the forecast now falls under the cash reserve, the card is frozen before the vendor can bill it.",
  },
  {
    key: "8", n: "8", short: "The money arrives", title: "The money arrives",
    why: "The deposit lands, the forecast is checked again, and the card is unfrozen if cash clears the reserve.",
  },
];

export const chapterFor = (key) => CHAPTERS.find((c) => c.key === key);
