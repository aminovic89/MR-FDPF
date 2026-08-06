from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


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
