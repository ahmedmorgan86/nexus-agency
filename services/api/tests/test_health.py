from fastapi.testclient import TestClient
from app.main import app, FEATURES

client = TestClient(app)
VALID = {"PRODUCTION_READY", "IMPLEMENTED_NOT_CONFIGURED", "PARTIALLY_IMPLEMENTED", "NOT_IMPLEMENTED", "FAILED"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_features_are_honest():
    r = client.get("/features")
    assert r.json() == FEATURES
    assert set(r.json().values()) <= VALID
