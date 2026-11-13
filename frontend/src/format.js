export const money = (n) =>
  Number(n ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const short = (n) => {
  const v = Number(n);
  return Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(v % 1000 === 0 ? 0 : 1)}k` : `${v}`;
};

// Groups the flat event stream into scenes.
export function groupScenes(events) {
  const scenes = [];
  events.forEach((e, i) => {
    if (e.event === "scene" || scenes.length === 0) {
      scenes.push({ title: e.event === "scene" ? e.title : "Run", items: [] });
      if (e.event === "scene") return;
    }
    scenes[scenes.length - 1].items.push({ ...e, _i: i });
  });
  return scenes;
}

export function summarize(events) {
  const rows = events.filter((e) => e.event === "charge" || e.event === "checkout");
  const unexpected = rows.filter((e) => !e.as_expected).length;
  return { rows: rows.length, unexpected, expected: rows.length - unexpected };
}

// Card state derived from the events so far.
export function cardState(events) {
  const card = { id: null, quote: null, status: null, reason: null, limits: null };
  for (const e of events) {
    if (e.event === "card_issued") Object.assign(card, { id: e.card_id, quote: e.quote, status: "ACTIVE" });
    if (e.event === "card_updated") card.quote = e.quote;
    if (e.event === "card_status") Object.assign(card, { status: e.status, reason: e.reason });
    if (e.event === "limits") card.limits = e;
  }
  return card;
}

export const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
