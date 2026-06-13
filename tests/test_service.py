import io

import pytest

import app as app_module
import service as service_module

VALID_BODY = {
    "description": "An introductory college course in Python programming, covering variables.",
    "weeks": 14,
}


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture
def fake_schedule(monkeypatch):
    """Stub the domain logic so service tests stay fast and offline, and
    ensure auth is open unless a test sets API_KEY itself."""
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(
        "knowledge.schedule.build_schedule",
        lambda description, weeks: {
            "subject": "Python",
            "weeks": [{"week": 1, "topics": ["X"]}],
            "topics": [],
            "citations": [],
            "confidence": "high",
        },
    )


def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True and data["version"]
    assert "/api/v1/schedule" in data["endpoints"]


def test_openapi_spec(client):
    spec = client.get("/api/v1/openapi.json").get_json()
    assert {"/api/v1/health", "/api/v1/schedule", "/api/v1/materials"} <= set(spec["paths"])
    assert spec["components"]["securitySchemes"]["ApiKeyAuth"]["name"] == "X-API-Key"


def test_schedule_happy_path(client, fake_schedule):
    res = client.post("/api/v1/schedule", json=VALID_BODY)
    assert res.status_code == 200
    assert res.get_json()["subject"] == "Python"


def test_old_alias_still_works(client, fake_schedule):
    assert client.post("/api/schedule", json=VALID_BODY).status_code == 200


def test_validation_error_envelope(client, fake_schedule):
    res = client.post("/api/v1/schedule", json={"description": "too short", "weeks": 14})
    assert res.status_code == 400
    error = res.get_json()["error"]
    assert error["code"] == "invalid_request" and error["message"]


def test_auth_open_when_key_unset(client, fake_schedule):
    assert client.post("/api/v1/schedule", json=VALID_BODY).status_code == 200


def test_auth_enforced_when_key_set(client, fake_schedule, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    assert client.post("/api/v1/schedule", json=VALID_BODY).status_code == 401
    assert (
        client.post("/api/v1/schedule", json=VALID_BODY, headers={"X-API-Key": "wrong"}).status_code
        == 401
    )
    assert (
        client.post("/api/v1/schedule", json=VALID_BODY, headers={"X-API-Key": "secret"}).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/schedule", json=VALID_BODY, headers={"Authorization": "Bearer secret"}
        ).status_code
        == 200
    )


def test_unauthorized_envelope(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    res = client.post("/api/v1/schedule", json=VALID_BODY)
    assert res.status_code == 401
    assert res.get_json()["error"]["code"] == "unauthorized"


def test_cors_headers_and_preflight(client):
    res = client.get("/api/v1/health")
    assert res.headers["Access-Control-Allow-Origin"] == "*"
    assert "X-API-Key" in res.headers["Access-Control-Allow-Headers"]
    preflight = client.open("/api/v1/schedule", method="OPTIONS")
    assert preflight.status_code in (200, 204)
    assert preflight.headers["Access-Control-Allow-Origin"] == "*"


def test_cors_allowlist(client, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.com, https://b.com")
    assert (
        client.get("/api/v1/health", headers={"Origin": "https://b.com"}).headers[
            "Access-Control-Allow-Origin"
        ]
        == "https://b.com"
    )
    # An origin not on the list never gets echoed back.
    assert (
        client.get("/api/v1/health", headers={"Origin": "https://evil.com"}).headers[
            "Access-Control-Allow-Origin"
        ]
        == "https://a.com"
    )


def test_materials_route_serves_zip(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(
        service_module, "build_materials", lambda data: (b"PK\x03\x04fake", {"units": 2})
    )
    res = client.post(
        "/api/v1/materials",
        data={"project": (io.BytesIO(b"zipbytes"), "project.zip")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert res.mimetype == "application/zip"
    assert res.data == b"PK\x03\x04fake"


def test_materials_requires_file(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    res = client.post("/api/v1/materials", data={}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_request"


def test_unknown_path_returns_json_404(client):
    res = client.get("/api/v1/nope")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "not_found"
