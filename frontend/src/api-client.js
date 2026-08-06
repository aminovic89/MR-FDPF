const API_BASE = "/api";

export async function fetchMaterials() {
  const res = await fetch(`${API_BASE}/materials`);
  if (!res.ok) throw new Error("failed to fetch materials");
  return res.json();
}

export async function simulate(payload) {
  const res = await fetch(`${API_BASE}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail)
      ? err.detail.map((d) => d.msg).join(", ")
      : err.detail;
    throw new Error(detail || `simulate failed (${res.status})`);
  }
  return res.json();
}
