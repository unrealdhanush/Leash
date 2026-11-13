const BASE = `${import.meta.env.REACT_APP_BACKEND_URL}/api`;

async function call(path, options = {}) {
  const headers = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const res = await fetch(`${BASE}${path}`, { headers, ...options });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.[0]?.msg || `HTTP ${res.status}`);
  }
  return body;
}

const post = (path, body) => call(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  health: () => call("/health"),
  context: () => call("/context"),
  runs: () => call("/runs"),
  run: (id) => call(`/runs/${id}`),
  start: (body) => post("/runs", body),
  streamUrl: (id, after) => `${BASE}/runs/${id}/stream?after=${after}`,
  decide: (id, approved, digest, note) => post(`/runs/${id}/approval`, { approved, digest, note }),
  extract: (file) => {
    const form = new FormData();
    form.append("file", file);
    return call("/quotes/extract", { method: "POST", body: form });
  },
  exportUrl: (id) => `${BASE}/runs/${id}/export`,
  share: (id) => post(`/runs/${id}/share`, {}),
  unshare: (id) => call(`/runs/${id}/share`, { method: "DELETE" }),
  shared: (token) => call(`/shared/${token}`),
};
