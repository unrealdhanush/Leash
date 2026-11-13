const BASE = `${import.meta.env.REACT_APP_BACKEND_URL}/api`;

async function call(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.detail || `HTTP ${res.status}`);
  return body;
}

export const api = {
  health: () => call("/health"),
  latest: () => call("/runs/latest"),
  start: (auto) => call("/runs", { method: "POST", body: JSON.stringify({ auto }) }),
  poll: (id, after) => call(`/runs/${id}?after=${after}`),
  decide: (id, approved) => call(`/runs/${id}/approval`, { method: "POST", body: JSON.stringify({ approved }) }),
};
