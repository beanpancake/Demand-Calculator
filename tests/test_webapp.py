from fastapi.testclient import TestClient
from webapp.server import app

client = TestClient(app)


def test_calculate_endpoint():
    payload = {
        "voltage": 240,
        "area": 100,
        "range": 40,
        "heat": 4000,
        "ac": 2000,
        "evse": 0,
        "additional": [2000],
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 18500.0
    assert data["basic"] == 6000.0


def test_report_endpoint_returns_pdf():
    payload = {"voltage": 240, "area": 90}
    resp = client.post("/report", json=payload)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")

