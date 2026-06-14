import json

import pytest

from knowledge import artifacts

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture
def blob_enabled(monkeypatch):
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "test-token")
    monkeypatch.delenv("ARCHIVE_ARTIFACTS", raising=False)


def test_enabled_requires_token_and_respects_toggle(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    assert artifacts.enabled() is False
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "tok")
    assert artifacts.enabled() is True
    monkeypatch.setenv("ARCHIVE_ARTIFACTS", "0")
    assert artifacts.enabled() is False


def test_store_artifact_uploads_file_and_sibling_metadata(blob_enabled, monkeypatch):
    puts = []

    def fake_put(url, data=None, headers=None, timeout=None):
        puts.append({"url": url, "headers": headers})
        return FakeResponse({"url": url, "downloadUrl": url + "?dl", "pathname": url})

    monkeypatch.setattr(artifacts.requests, "put", fake_put)

    info = artifacts.store_artifact("lecture", "req123", b"PPTXBYTES", PPTX, {"title": "Intro"})

    assert info and info["url"].endswith("req123.pptx")
    assert info["downloadUrl"].endswith("?dl")
    # Two uploads: the artifact, then its <name>.json metadata sibling.
    assert len(puts) == 2
    assert puts[0]["url"].endswith("artifacts/lecture/") is False  # has date + filename
    assert "artifacts/lecture/" in puts[0]["url"] and puts[0]["url"].endswith("req123.pptx")
    assert puts[1]["url"].endswith("req123.pptx.json")
    # Auth + version headers present; token in header only (never in the record).
    assert puts[0]["headers"]["authorization"] == "Bearer test-token"
    assert "x-api-version" in puts[0]["headers"]


def test_store_artifact_disabled_returns_none(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    assert artifacts.store_artifact("lecture", "r", b"x", "application/zip", {}) is None


def test_store_artifact_swallows_errors(blob_enabled, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(artifacts.requests, "put", boom)
    assert artifacts.store_artifact("lecture", "r", b"x", "application/zip", {}) is None


def test_list_artifacts_filters_meta_and_inlines_metadata(blob_enabled, monkeypatch):
    blobs = {
        "blobs": [
            {"pathname": "artifacts/lecture/2026-06-14/a.pptx", "url": "https://blob/a.pptx",
             "size": 100, "uploadedAt": "2026-06-14T10:00:00Z"},
            {"pathname": "artifacts/lecture/2026-06-14/a.pptx.json", "url": "https://blob/a.pptx.json",
             "size": 50, "uploadedAt": "2026-06-14T10:00:00Z"},
            {"pathname": "artifacts/materials/2026-06-13/b.zip", "url": "https://blob/b.zip",
             "size": 200, "uploadedAt": "2026-06-13T09:00:00Z"},
        ]
    }

    def fake_get(url, headers=None, params=None, timeout=None):
        if url == artifacts.BLOB_BASE:
            return FakeResponse(blobs)
        return FakeResponse({"title": "Intro", "kind": "lecture"})  # the metadata fetch

    monkeypatch.setattr(artifacts.requests, "get", fake_get)

    result = artifacts.list_artifacts()

    assert [a["name"] for a in result] == ["a.pptx", "b.zip"]   # .json filtered, newest first
    assert result[0]["metadata"]["title"] == "Intro"            # sibling metadata inlined
    assert result[1]["metadata"] == {}                          # no sibling for b.zip


def test_list_artifacts_disabled_returns_empty(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    assert artifacts.list_artifacts() == []
