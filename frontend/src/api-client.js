const API_BASE = "/api";

export async function fetchMaterials() {
  const res = await fetch(`${API_BASE}/materials`);
  if (!res.ok) throw new Error("failed to fetch materials");
  return res.json();
}

async function post(path, payload) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const detail = Array.isArray(err.detail)
      ? err.detail.map((d) => d.msg).join(", ")
      : err.detail;
    throw new Error(detail || `request failed (${res.status})`);
  }
  return res.json();
}

export async function simulate(payload) {
  return post("/simulate", payload);
}

export async function simulateBuilding(payload) {
  return post("/simulate_building", payload);
}

export async function startSimulateBuilding(payload) {
  return post("/simulate_building/start", payload);
}

export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error(`job status failed (${res.status})`);
  return res.json();
}
