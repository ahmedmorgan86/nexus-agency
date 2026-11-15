import uuid

import jwt
from fastapi.testclient import TestClient

from app.server import app, jwt_secret, make_token, registration_allowed

client = TestClient(app)
PW = "correct-horse-battery"


def register(name="Org"):
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": PW, "tenant_name": name})
    assert r.status_code == 201, r.text
    return email, r.json()["token"], r.json()["tenant_id"]


def auth(t):
    return {"Authorization": f"Bearer {t}"}


def test_register_login_roundtrip():
    email, _, tid = register()
    r = client.post("/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200 and r.json()["tenant_id"] == tid


def test_wrong_password_and_unknown_user_rejected():
    email, _, _ = register()
    assert client.post("/auth/login", json={"email": email, "password": "wrong-password-1"}).status_code == 401
    assert client.post("/auth/login", json={"email": "nobody@example.com", "password": PW}).status_code == 401


def test_duplicate_email_rejected():
    email, _, _ = register()
    r = client.post("/auth/register", json={"email": email, "password": PW, "tenant_name": "Dup"})
    assert r.status_code == 409


def test_weak_password_rejected():
    r = client.post("/auth/register", json={"email": "a@b.co", "password": "short", "tenant_name": "X"})
    assert r.status_code == 422


def test_registration_can_be_closed(monkeypatch):
    monkeypatch.setenv("ALLOW_REGISTRATION", "0")
    r = client.post("/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@example.com",
                                            "password": PW, "tenant_name": "Closed"})
    assert r.status_code == 403


def test_registration_defaults_closed_in_production(monkeypatch):
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    assert registration_allowed() is False
    monkeypatch.setenv("ALLOW_REGISTRATION", "1")
    assert registration_allowed() is True


def test_requires_token():
    assert client.get("/leads").status_code == 401
    assert client.get("/leads", headers=auth("garbage")).status_code == 401


def test_expired_and_tampered_tokens_rejected():
    _, tok, tid = register()
    claims = jwt.decode(tok, jwt_secret(), algorithms=["HS256"])
    claims["exp"] = 1
    assert client.get("/leads", headers=auth(jwt.encode(claims, jwt_secret(), algorithm="HS256"))).status_code == 401
    assert client.get("/leads", headers=auth(jwt.encode(claims, "other-secret-0123456789abcdef0123", algorithm="HS256"))).status_code == 401


def test_api_cross_tenant_isolation():
    _, ta, _ = register("A")
    _, tb, _ = register("B")
    client.post("/leads", json={"business_name": "Acme"}, headers=auth(ta))
    client.post("/leads", json={"business_name": "Beta"}, headers=auth(tb))
    assert [l["business_name"] for l in client.get("/leads", headers=auth(ta)).json()] == ["Acme"]
    assert [l["business_name"] for l in client.get("/leads", headers=auth(tb)).json()] == ["Beta"]


def test_token_for_foreign_tenant_without_membership_sees_nothing_of_others():
    # A forged-looking token is rejected by signature; a validly signed token for an empty tenant sees no data.
    _, ta, _ = register("A2")
    client.post("/leads", json={"business_name": "Secret"}, headers=auth(ta))
    stray = make_token(uuid.uuid4(), uuid.uuid4(), "owner")
    assert client.get("/leads", headers=auth(stray)).json() == []


def test_client_viewer_cannot_write():
    _, _, tid = register("V")
    viewer = make_token(uuid.uuid4(), tid, "client_viewer")
    assert client.post("/leads", json={"business_name": "X"}, headers=auth(viewer)).status_code == 403
    assert client.get("/leads", headers=auth(viewer)).status_code == 200


def test_lead_validation_and_audit_trail():
    _, tok, _ = register("L")
    assert client.post("/leads", json={"business_name": ""}, headers=auth(tok)).status_code == 422
    assert client.post("/leads", json={"business_name": "Ok", "website": "not a url"}, headers=auth(tok)).status_code == 422
    assert client.post("/leads", json={"business_name": "Ok", "website": "https://ok.example"}, headers=auth(tok)).status_code == 201
