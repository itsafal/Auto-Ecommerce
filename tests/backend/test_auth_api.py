from __future__ import annotations

from fastapi.testclient import TestClient

from backend.db.clickhouse import reset_client_for_tests
from backend.db.memory_store import get_memory_store
from backend.main import app


def setup_function() -> None:
    reset_client_for_tests()
    get_memory_store().reset()


def test_signup_creates_user_and_token(monkeypatch) -> None:
    monkeypatch.setenv("USE_CLICKHOUSE", "false")
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    client = TestClient(app)

    response = client.post(
        "/api/auth/signup",
        json={"email": "Owner@FastAISolution.com", "password": "correct horse battery", "full_name": "Store Owner"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == "owner@fastaisolution.com"
    assert payload["user"]["full_name"] == "Store Owner"


def test_signup_rejects_duplicate_email(monkeypatch) -> None:
    monkeypatch.setenv("USE_CLICKHOUSE", "false")
    client = TestClient(app)
    body = {"email": "owner@fastaisolution.com", "password": "correct horse battery", "full_name": ""}

    assert client.post("/api/auth/signup", json=body).status_code == 201
    response = client.post("/api/auth/signup", json=body)

    assert response.status_code == 409


def test_login_and_me_round_trip(monkeypatch) -> None:
    monkeypatch.setenv("USE_CLICKHOUSE", "false")
    monkeypatch.setenv("AUTH_SECRET", "test-secret")
    client = TestClient(app)
    client.post(
        "/api/auth/signup",
        json={"email": "owner@fastaisolution.com", "password": "correct horse battery", "full_name": "Store Owner"},
    )

    login = client.post("/api/auth/login", json={"email": "owner@fastaisolution.com", "password": "correct horse battery"})
    token = login.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert login.status_code == 200
    assert me.status_code == 200
    assert me.json()["email"] == "owner@fastaisolution.com"


def test_login_rejects_wrong_password(monkeypatch) -> None:
    monkeypatch.setenv("USE_CLICKHOUSE", "false")
    client = TestClient(app)
    client.post(
        "/api/auth/signup",
        json={"email": "owner@fastaisolution.com", "password": "correct horse battery", "full_name": ""},
    )

    response = client.post("/api/auth/login", json={"email": "owner@fastaisolution.com", "password": "wrong password"})

    assert response.status_code == 401


def test_signup_rejects_disallowed_email_domain(monkeypatch) -> None:
    monkeypatch.setenv("USE_CLICKHOUSE", "false")
    client = TestClient(app)

    response = client.post(
        "/api/auth/signup",
        json={"email": "outsider@gmail.com", "password": "correct horse battery", "full_name": ""},
    )

    assert response.status_code == 403
    assert "fastaisolution.com" in response.json()["detail"].lower()


def test_me_rejects_invalid_token(monkeypatch) -> None:
    monkeypatch.setenv("USE_CLICKHOUSE", "false")
    client = TestClient(app)

    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
