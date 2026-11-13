const BASE = `${import.meta.env.REACT_APP_BACKEND_URL}/api`;
const LIVE = ["running", "waiting_approval"];

let getToken = async () => null;
export const setTokenGetter = (fn) => {
  getToken = fn;
};

async function authHeaders() {
  const token = await getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function call(path, options = {}) {
  const json = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const res = await fetch(`${BASE}${path}`, { ...options, headers: { ...json, ...(await authHeaders()) } });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.[0]?.msg || `HTTP ${res.status}`);
  }
  return body;
}

const send = (method, path, body) => call(path, { method, body: JSON.stringify(body) });

// Reads a run's server-sent event stream with the session token; reconnects from the last event seen.
function stream(id, after, { onEvent, onState, onLost }) {
  const control = new AbortController();
  let count = after;
  let finished = false;

  const read = async () => {
    const res = await fetch(`${BASE}/runs/${id}/stream?after=${count}`, { headers: await authHeaders(), signal: control.signal });
    if (!res.ok) return false;
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return true;
      buffer += value;
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, cut);
        buffer = buffer.slice(cut + 2);
        const type = /^event: (.*)$/m.exec(block)?.[1];
        const data = /^data: (.*)$/m.exec(block)?.[1];
        if (!type || !data) continue;
        if (type === "leash") {
          count += 1;
          onEvent(JSON.parse(data));
        } else {
          const state = JSON.parse(data);
          finished = !LIVE.includes(state.status);
          onState(state);
        }
      }
    }
  };

  (async () => {
    let failures = 0;
    while (!finished && !control.signal.aborted && failures < 5) {
      const ok = await read().catch(() => null);
      if (ok === false) break;
      failures = ok ? 0 : failures + 1;
      if (!finished) await new Promise((r) => setTimeout(r, 1000));
    }
    if (!finished && !control.signal.aborted) onLost();
  })();
  return () => control.abort();
}

async function download(id) {
  const res = await fetch(`${BASE}/runs/${id}/export`, { headers: await authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const name = /filename="(.+?)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || `leash-purchase-${id}.json`;
  const link = document.createElement("a");
  link.href = URL.createObjectURL(await res.blob());
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

export const api = {
  health: () => call("/health"),
  me: () => call("/me"),
  users: () => call("/users"),
  setRole: (userId, role) => send("PATCH", `/users/${userId}/role`, { role }),
  context: () => call("/context"),
  runs: () => call("/runs"),
  run: (id) => call(`/runs/${id}`),
  start: (body) => send("POST", "/runs", body),
  stream,
  decide: (id, approved, digest, note) => send("POST", `/runs/${id}/approval`, { approved, digest, note }),
  extract: (file) => {
    const form = new FormData();
    form.append("file", file);
    return call("/quotes/extract", { method: "POST", body: form });
  },
  download,
  share: (id) => send("POST", `/runs/${id}/share`, {}),
  unshare: (id) => call(`/runs/${id}/share`, { method: "DELETE" }),
  shared: (token) => call(`/shared/${token}`),
};
