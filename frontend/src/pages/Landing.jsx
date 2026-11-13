import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CreditCard, FileSearch, UserCheck } from "lucide-react";
import { CHAPTERS } from "../chapters.js";

const PRINCIPLES = [
  {
    icon: FileSearch,
    title: "The model reads. Code decides.",
    text: "Claude pulls the prices out of the vendor's email, and every price has to appear word for word in the quote or the read is rejected. Which option is allowed is decided by policy code, never by a prompt.",
  },
  {
    icon: UserCheck,
    title: "People approve exact terms.",
    text: "When something breaks policy, a person sees the vendor, the amount and the reason. Their approval is bound to those terms. If the price changes, the old approval no longer counts.",
  },
  {
    icon: CreditCard,
    title: "The card enforces it.",
    text: "Each purchase gets its own virtual card with the amount, currency and merchant type set at the issuer. A charge outside the decision is declined by the card, not by a dashboard alert afterwards.",
  },
];

export default function Landing() {
  return (
    <div className="landing" data-testid="landing-page">
      <header className="nav">
        <Link to="/" className="brand"><span className="mark">L</span><span className="brand-name">Leash</span></Link>
        <nav className="nav-links"><a href="#flow" data-testid="landing-nav-flow">How a purchase flows</a><a href="#control" data-testid="landing-nav-control">What keeps it safe</a></nav>
        <div className="nav-right"><Link to="/app" className="btn primary" data-testid="landing-open-app-nav">Open Leash</Link></div>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">For finance teams</p>
          <h1>Let an agent buy the software. Keep the card on a leash.</h1>
          <p className="hero-sub">
            Leash reads the vendor's quote, checks it against your spending policy and your cash forecast, and issues a virtual card
            that can only pay what was decided.
          </p>
          <div className="hero-cta">
            <Link to="/app" className="btn primary big" data-testid="landing-open-app-hero">Open Leash <ArrowRight size={16} /></Link>
            <a href="#flow" className="btn big ghost" data-testid="landing-see-flow">See how a purchase flows</a>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <pre className="email art-email">{"You can pay monthly at $1,000 per month, billed on the 1st.\n\nOr you can save 18% by paying annually: $9,840 billed once up front for 12 months."}</pre>
          <div className="art-decision">
            <span className="art-tag">Policy</span>
            <b>monthly</b> is within policy. <span className="dim">annual is over the 5,000.00 limit and goes to a person.</span>
          </div>
          <div className="panel vcard art-card">
            <div className="vcard-top"><span>Virtual card</span><span className="badge expected">ACTIVE</span></div>
            <div className="art-vendor">Northwind Analytics</div>
            <div className="vcard-grid">
              <span>Limit</span><b className="mono">1,000.00 USD per charge</b>
              <span>Currency</span><b className="mono">USD only</b>
              <span>Merchant</span><b className="mono">MCC 5734 only</b>
            </div>
          </div>
          <p className="art-caption mono">from the example quote that ships with Leash</p>
        </div>
      </section>

      <section className="lsec" id="flow">
        <p className="eyebrow">How a purchase flows</p>
        <h2>From an email to a card, and everything that can go wrong after.</h2>
        <ol className="flow">
          {CHAPTERS.slice(1).map((c) => (
            <li key={c.key} data-testid={`landing-step-${c.key}`}>
              <span className="flow-n mono">{c.n}</span>
              <h3>{c.title}</h3>
              <p>{c.why}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="lsec" id="control">
        <p className="eyebrow">What keeps it safe</p>
        <h2>Three places a mistake gets stopped.</h2>
        <div className="principles">
          {PRINCIPLES.map(({ icon: Icon, title, text }) => (
            <article key={title}>
              <Icon size={20} />
              <h3>{title}</h3>
              <p>{text}</p>
            </article>
          ))}
        </div>
        <p className="built mono">
          Cards and balances run on the Airwallex sandbox. Quotes are read by Claude. Checkout uses Visa Trusted Agent Protocol message
          signatures, with a local key directory and a mock merchant standing in for Visa's.
        </p>
      </section>

      <section className="lsec closing">
        <h2>Start with one quote.</h2>
        <p>Open the app, hand the quote to the agent and watch each step as it happens. You stay the one who says yes.</p>
        <Link to="/app" className="btn primary big" data-testid="landing-open-app-footer">Open Leash <ArrowRight size={16} /></Link>
      </section>
      <footer className="lfoot"><span className="brand-name">Leash</span><span className="dim small">Purchase agent with a card that only pays what was decided.</span></footer>
    </div>
  );
}
