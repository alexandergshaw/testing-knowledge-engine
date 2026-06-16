import json

import pytest

import app as app_module
import observability
import service as service_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture
def records(monkeypatch):
    """Capture every access-log record instead of writing it to stdout."""
    captured = []
    monkeypatch.setattr(observability, "_emit", captured.append)
    monkeypatch.delenv("API_KEY", raising=False)
    return captured


def test_one_structured_record_per_request(client, records):
    client.get("/api/v1/health")
    assert len(records) == 1
    rec = records[0]
    assert rec["event"] == "api_call"
    assert rec["method"] == "GET"
    assert rec["path"] == "/api/v1/health"
    assert rec["status"] == 200
    assert rec["request_id"]
    assert isinstance(rec["duration_ms"], (int, float))


def test_api_key_is_never_logged(client, records):
    client.get("/api/v1/health", headers={"X-API-Key": "supersecret"})
    rec = records[0]
    assert rec["api_key_present"] is True
    assert "supersecret" not in json.dumps(rec)  # only presence, never the value


def test_json_bodies_captured(client, records, monkeypatch):
    monkeypatch.setattr(
        "knowledge.schedule.build_schedule",
        lambda *a, **k: {"subject": "Python", "weeks": [], "topics": [], "citations": [], "confidence": "high"},
    )
    client.post("/api/v1/schedule", json={"description": "Intro to Python programming.", "weeks": 14})
    rec = records[0]
    assert "Intro to Python" in rec["request_body"]
    assert "Python" in rec["response_body"]


def test_payload_truncation(client, records, monkeypatch):
    monkeypatch.setenv("LOG_PAYLOAD_MAX_BYTES", "20")
    monkeypatch.setattr(
        "knowledge.schedule.build_schedule",
        lambda *a, **k: {"subject": "X", "weeks": [], "topics": [], "citations": [], "confidence": "high"},
    )
    client.post(
        "/api/v1/schedule",
        json={"description": "A description that is well over twenty bytes long.", "weeks": 14},
    )
    assert "truncated" in records[0]["request_body"]


def test_binary_response_logs_size_not_body(client, records, monkeypatch):
    # A .pptx response must never have its bytes read into the log.
    monkeypatch.setattr(
        service_module, "build_lecture_deck",
        lambda objectives, title, **kwargs: (b"PKBINARYDATA", {"objectives": 1})
    )
    client.post("/api/v1/lecture", json={"objectives": "Define variables and explain control flow."})
    rec = records[0]
    assert rec["response_body"] is None
    assert rec["resp_bytes"] == len(b"PKBINARYDATA")


def test_error_status_raises_log_level(client, records):
    client.post("/api/v1/schedule", json={"description": "too short", "weeks": 14})
    assert records[0]["status"] == 400  # validation error still logged (as WARNING)
