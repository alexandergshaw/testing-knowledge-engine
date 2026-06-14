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
        lambda description, weeks, start_date=None, tests=0, term=None: {
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


@pytest.fixture
def capture_schedule(monkeypatch):
    """Capture the args build_schedule is called with, without network."""
    captured = {}
    monkeypatch.delenv("API_KEY", raising=False)

    def fake(description, weeks, start_date=None, tests=0, term=None):
        captured.update(
            description=description, weeks=weeks, start_date=start_date, tests=tests, term=term
        )
        return {"subject": "X", "weeks": [], "topics": [], "citations": [], "confidence": "low"}

    monkeypatch.setattr("knowledge.schedule.build_schedule", fake)
    return captured


def test_schedule_backward_compatible_defaults(client, capture_schedule):
    res = client.post("/api/v1/schedule", json=VALID_BODY)
    assert res.status_code == 200
    assert capture_schedule["start_date"] is None
    assert capture_schedule["tests"] == 0
    assert capture_schedule["term"] is None


def test_schedule_passes_through_new_fields(client, capture_schedule):
    res = client.post(
        "/api/v1/schedule",
        json={**VALID_BODY, "startDate": "2026-08-24", "tests": 2, "term": "Fall 2026"},
    )
    assert res.status_code == 200
    import datetime

    assert capture_schedule["start_date"] == datetime.date(2026, 8, 24)
    assert capture_schedule["tests"] == 2
    assert capture_schedule["term"] == "Fall 2026"


def test_schedule_rejects_bad_start_date(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    res = client.post("/api/v1/schedule", json={**VALID_BODY, "startDate": "not-a-date"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_request"


def test_schedule_rejects_negative_tests(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    res = client.post("/api/v1/schedule", json={**VALID_BODY, "tests": -1})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_request"


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


def test_artifacts_endpoint_lists(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(service_module.artifacts, "enabled", lambda: True)
    monkeypatch.setattr(
        service_module.artifacts,
        "list_artifacts",
        lambda: [{"name": "a.pptx", "url": "u", "downloadUrl": "u", "size": 1,
                  "uploadedAt": "t", "metadata": {}}],
    )
    res = client.get("/api/v1/artifacts")
    assert res.status_code == 200
    data = res.get_json()
    assert data["enabled"] is True
    assert data["artifacts"][0]["name"] == "a.pptx"


def test_artifacts_endpoint_is_auth_gated(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    res = client.get("/api/v1/artifacts")
    assert res.status_code == 401


def test_artifacts_disabled_without_blob(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    res = client.get("/api/v1/artifacts")
    assert res.status_code == 200
    assert res.get_json() == {"enabled": False, "artifacts": []}


def test_openapi_includes_artifacts(client):
    spec = client.get("/api/v1/openapi.json").get_json()
    assert "/api/v1/artifacts" in spec["paths"]
