"""Durable storage for generated artifacts (.pptx lectures, .zip materials) on
Vercel Blob, so every generated file stays downloadable/viewable after the call.

No new dependency: it talks to the Blob REST API with `requests` (already used by
the source adapters). Entirely best-effort — when BLOB_READ_WRITE_TOKEN is unset
(local dev) or a call fails, nothing is stored and the caller is never affected.
The hard no-LLM rule is untouched; this is plain object storage.

Layout in the store:
  artifacts/<kind>/<YYYY-MM-DD>/<request_id>.<ext>        the file itself
  artifacts/<kind>/<YYYY-MM-DD>/<request_id>.<ext>.json   its request metadata
"""

import json
import logging
import os
from datetime import date, datetime, timezone

import requests

log = logging.getLogger(__name__)

BLOB_BASE = "https://blob.vercel-storage.com"
# The Blob REST API is versioned via this header. Overridable via env so it can
# be corrected without a code change if Vercel bumps it.
BLOB_API_VERSION = os.environ.get("BLOB_API_VERSION", "7")
PREFIX = "artifacts"
REQUEST_TIMEOUT = 10
LIST_LIMIT = 50

_EXT = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/zip": "zip",
}


def _token():
    return os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()


def enabled():
    """True when artifact archiving is configured (token present) and not
    explicitly disabled via ARCHIVE_ARTIFACTS=0."""
    if os.environ.get("ARCHIVE_ARTIFACTS", "1").strip() == "0":
        return False
    return bool(_token())


def _headers(extra=None):
    headers = {"authorization": f"Bearer {_token()}", "x-api-version": BLOB_API_VERSION}
    if extra:
        headers.update(extra)
    return headers


def _put(pathname, data, content_type):
    response = requests.put(
        f"{BLOB_BASE}/{pathname}",
        data=data,
        headers=_headers(
            {
                "x-content-type": content_type,
                # Keep our deterministic <request_id>.<ext> path (no random suffix)
                # so the sibling .json metadata is addressable.
                "x-add-random-suffix": "0",
            }
        ),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def store_artifact(kind, request_id, data, content_type, metadata=None):
    """Upload one generated artifact, plus a sibling .json of its request
    metadata. Returns {url, downloadUrl, pathname} or None. Never raises —
    archiving must not affect the user's download."""
    if not enabled():
        return None
    try:
        ext = _EXT.get(content_type, "bin")
        pathname = f"{PREFIX}/{kind}/{date.today().isoformat()}/{request_id}.{ext}"
        result = _put(pathname, data, content_type)
        info = {
            "url": result.get("url"),
            "downloadUrl": result.get("downloadUrl") or result.get("url"),
            "pathname": result.get("pathname", pathname),
        }
        if metadata is not None:
            meta = dict(metadata)
            meta.update(
                {
                    "kind": kind,
                    "requestId": request_id,
                    "storedAt": datetime.now(timezone.utc).isoformat(),
                    "artifactUrl": info["url"],
                    "size": len(data),
                }
            )
            try:
                _put(pathname + ".json", json.dumps(meta).encode("utf-8"), "application/json")
            except Exception:
                log.warning("artifact metadata upload failed", exc_info=True)
        return info
    except Exception:
        log.warning("artifact upload failed", exc_info=True)
        return None


def list_artifacts(limit=LIST_LIMIT):
    """Recent stored artifacts, newest first, each with its request metadata
    inlined. Returns [] when disabled or on failure."""
    if not enabled():
        return []
    try:
        response = requests.get(
            BLOB_BASE,
            headers=_headers(),
            params={"prefix": f"{PREFIX}/", "limit": str(limit)},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        blobs = response.json().get("blobs", [])
    except Exception:
        log.warning("artifact listing failed", exc_info=True)
        return []

    meta_urls = {
        b.get("pathname"): b.get("url")
        for b in blobs
        if str(b.get("pathname", "")).endswith(".json")
    }
    artifacts = []
    for blob in blobs:
        pathname = str(blob.get("pathname", ""))
        if pathname.endswith(".json"):
            continue
        entry = {
            "pathname": pathname,
            "name": pathname.rsplit("/", 1)[-1],
            "url": blob.get("url"),
            "downloadUrl": blob.get("downloadUrl") or blob.get("url"),
            "size": blob.get("size"),
            "uploadedAt": blob.get("uploadedAt"),
            "metadata": {},
        }
        meta_url = meta_urls.get(pathname + ".json")
        if meta_url:
            try:
                entry["metadata"] = requests.get(meta_url, timeout=REQUEST_TIMEOUT).json()
            except Exception:
                pass
        artifacts.append(entry)
    artifacts.sort(key=lambda a: a.get("uploadedAt") or "", reverse=True)
    return artifacts
