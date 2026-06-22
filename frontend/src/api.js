// Single seam between the UI and the backend. All backend calls go through here.

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

async function get(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return res.json();
}

async function post(path, body, headers = {}) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST", body, headers });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return res.json();
}

// ---- Health ----
export async function getHealth() {
  return get("/health");
}

// ---- Property (guest read) ----
export async function getProperty(id) {
  return get(`/property/${id}`);
}

export async function getPlaces(id) {
  return get(`/property/${id}/places`);
}

// ---- Admin: save property ----
export async function saveProperty(params) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== ""))
  ).toString();
  return get(`/manage-property?${qs}`);
}

// ---- Logo URL (served via Function App, not blob storage) ----
export function logoUrl(id) {
  return `${API_BASE}/logos/${id}`;
}

// ---- Admin: upload logo ----
export async function uploadLogo(id, adminToken, file) {
  return post(
    `/manage-upload/${id}?adminToken=${encodeURIComponent(adminToken)}`,
    file,
    { "Content-Type": file.type },
  );
}

export const usingStubs = !API_BASE;
