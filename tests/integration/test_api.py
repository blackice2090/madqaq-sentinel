from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_phantom_scenario_api():
    r = client.post("/m0/scenarios/phantom_completion_b/evaluate")
    assert r.status_code == 200
    body = r.json()
    assert body["violations"][0]["type"] == "PHANTOM_COMPLETION"
    assert body["violations"][0]["step_id"] == "B"
