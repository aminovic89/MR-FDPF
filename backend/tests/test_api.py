import time

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _poll_job(job_id: str, timeout_s: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] in ("done", "error"):
            return data
        time.sleep(0.05)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_s}s")


def test_list_materials():
    resp = client.get("/api/materials")
    assert resp.status_code == 200
    names = {m["name"] for m in resp.json()}
    assert "concrete" in names
    assert "metal" in names


def test_simulate_free_space():
    payload = {
        "width": 1.0,
        "height": 1.0,
        "walls": [],
        "sources": [{"x": 0.5, "y": 0.5, "power_dbm": 20.0}],
        "freq_mhz": 2400.0,
        "points_per_wavelength": 15,
        "mode": "single",
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["nx"] > 0 and data["ny"] > 0
    assert len(data["power_dbm"]) == data["ny"]
    assert len(data["power_dbm"][0]) == data["nx"]


def test_simulate_rejects_unknown_material():
    payload = {
        "width": 1.0,
        "height": 1.0,
        "walls": [{"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0, "material": "unobtainium"}],
        "sources": [{"x": 0.5, "y": 0.5}],
    }
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code == 400


def test_simulate_rejects_no_sources():
    payload = {"width": 1.0, "height": 1.0, "walls": [], "sources": []}
    resp = client.post("/api/simulate", json=payload)
    assert resp.status_code in (400, 422)


def test_simulate_building_two_floors():
    payload = {
        "width": 2.0,
        "height": 2.0,
        "floors": [
            {"walls": [], "sources": [{"x": 1.0, "y": 1.0, "power_dbm": 20.0}]},
            {"walls": [], "sources": []},
        ],
        "floor_attenuation_db": 12.0,
        "freq_mhz": 2400.0,
        "points_per_wavelength": 15,
        "mode": "single",
    }
    resp = client.post("/api/simulate_building", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["floors_power_dbm"]) == 2
    assert len(data["floors_power_dbm"][0]) == data["ny"]


def test_simulate_building_rejects_no_floors():
    resp = client.post("/api/simulate_building", json={"width": 1.0, "height": 1.0, "floors": []})
    assert resp.status_code in (400, 422)


def test_simulate_building_rejects_no_sources():
    payload = {"width": 1.0, "height": 1.0, "floors": [{"walls": [], "sources": []}]}
    resp = client.post("/api/simulate_building", json=payload)
    assert resp.status_code == 400


def test_async_job_matches_sync_result():
    payload = {
        "width": 2.0,
        "height": 2.0,
        "floors": [{"walls": [], "sources": [{"x": 1.0, "y": 1.0, "power_dbm": 20.0}]}],
        "freq_mhz": 2400.0,
        "points_per_wavelength": 15,
        "mode": "single",
    }
    sync_resp = client.post("/api/simulate_building", json=payload).json()

    start_resp = client.post("/api/simulate_building/start", json=payload)
    assert start_resp.status_code == 200
    job_id = start_resp.json()["job_id"]

    job = _poll_job(job_id)
    assert job["status"] == "done"
    assert job["progress"] == 1.0
    assert job["result"]["floors_power_dbm"] == sync_resp["floors_power_dbm"]


def test_async_job_reports_error_for_no_sources():
    payload = {"width": 1.0, "height": 1.0, "floors": [{"walls": [], "sources": []}]}
    resp = client.post("/api/simulate_building/start", json=payload)
    assert resp.status_code == 400


def test_job_not_found():
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404
