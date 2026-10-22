// src/api.js
// Thin fetch wrapper: attaches the JWT from AuthContext, talks to the
// backend through Vite's /api proxy (see vite.config.js).

const BASE = "/api";

export async function apiFetch(path, { method = "GET", token, params, body } = {}) {
  let url = BASE + path;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
    ).toString();
    if (qs) url += "?" + qs;
  }
  const res = await fetch(url, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || `Request failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

// POST endpoints in this backend take query params, not a JSON body
// (matches the FastAPI signatures written in the routers). This helper
// mirrors apiFetch but always sends as query params.
export async function apiCall(path, { method = "POST", token, params } = {}) {
  return apiFetch(path, { method, token, params });
}
