"""Per-request structured access logging for the API.

Emits one JSON line per request to stdout, which Vercel surfaces in Runtime Logs
/ Observability (filterable by field). Request and response JSON bodies are
captured — capped to LOG_PAYLOAD_MAX_BYTES and with auth headers never logged.
Binary (.pptx/.zip) responses are logged by size plus the stored artifact URL
(see knowledge/artifacts.py), so a generated file can be traced from its log line.

Config (env): LOG_LEVEL (INFO), LOG_PAYLOADS (1/0), LOG_PAYLOAD_MAX_BYTES (4096).
"""

import json
import logging
import os
import sys
import time
import uuid

from flask import g, request

ACCESS_LOGGER = "courseengine.access"
DEFAULT_MAX_BODY = 4096


def _max_body():
    try:
        return int(os.environ.get("LOG_PAYLOAD_MAX_BYTES", DEFAULT_MAX_BODY))
    except ValueError:
        return DEFAULT_MAX_BODY


def _payloads_enabled():
    return os.environ.get("LOG_PAYLOADS", "1").strip() != "0"


def _truncate(text):
    if text is None:
        return None
    cap = _max_body()
    if len(text) <= cap:
        return text
    return text[:cap] + f"…<truncated {len(text) - cap} bytes>"


def _capture_request_body():
    """JSON bodies only. For multipart we record the shape (field/file names) but
    NEVER read the stream here — doing so would consume the upload before the view
    parses it."""
    if not _payloads_enabled():
        return None
    ctype = request.content_type or ""
    if ctype.startswith("multipart/form-data"):
        files = {name: getattr(f, "filename", "") for name, f in request.files.items()}
        return {"multipart": True, "files": files, "fields": list(request.form.keys())}
    if "application/json" in ctype:
        # cache=True so the view's get_json() still sees the body.
        try:
            return _truncate(request.get_data(cache=True).decode("utf-8", "replace"))
        except Exception:
            return None
    return None


def _capture_response_body(response):
    if not _payloads_enabled():
        return None
    if response.direct_passthrough:  # send_file binary — never read its bytes
        return None
    ctype = response.mimetype or ""
    if "application/json" in ctype or ctype.startswith("text/"):
        try:
            return _truncate(response.get_data(as_text=True))
        except Exception:
            return None
    return None


def _client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def _level_for(status):
    if status >= 500:
        return logging.ERROR
    if status >= 400:
        return logging.WARNING
    return logging.INFO


def current_request_id():
    """The id for the in-flight request (Vercel's x-vercel-id, else a UUID).
    Stable within a request; created on first access."""
    rid = getattr(g, "_access_id", None)
    if not rid:
        rid = request.headers.get("x-vercel-id") or uuid.uuid4().hex
        g._access_id = rid
    return rid


def record_artifact(info):
    """Called by the service layer after archiving so this request's log line
    carries the stored artifact's URL."""
    if info:
        g._access_artifact = info


def _before():
    g._access_t0 = time.perf_counter()
    current_request_id()
    try:
        g._access_req_body = _capture_request_body()
    except Exception:
        g._access_req_body = None


def _after(response):
    started = getattr(g, "_access_t0", None)
    record = {
        "event": "api_call",
        "request_id": getattr(g, "_access_id", None),
        "method": request.method,
        "path": request.path,
        "route": str(request.url_rule) if request.url_rule else None,
        "status": response.status_code,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1) if started else None,
        "req_bytes": request.content_length,
        "resp_bytes": response.content_length,
        "req_content_type": request.content_type,
        "resp_content_type": response.mimetype,
        "client_ip": _client_ip(),
        # The key itself is never logged — only whether one was presented.
        "api_key_present": bool(
            request.headers.get("X-API-Key") or request.headers.get("Authorization")
        ),
    }
    if _payloads_enabled():
        record["request_body"] = getattr(g, "_access_req_body", None)
        record["response_body"] = _capture_response_body(response)
    artifact = getattr(g, "_access_artifact", None)
    if artifact:
        record["artifact"] = artifact
    _emit(record)
    return response


def _emit(record):
    logging.getLogger(ACCESS_LOGGER).log(
        _level_for(record.get("status", 200)), json.dumps(record, default=str)
    )


def configure(app):
    """Register the access-log hooks and a stdout handler that emits pure JSON
    lines (no logging prefix), so Vercel parses each line into fields."""
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    logger = logging.getLogger(ACCESS_LOGGER)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    app.before_request(_before)
    app.after_request(_after)
