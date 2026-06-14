"""HTTP service layer: the versioned `/api/v1` surface, request validation,
API-key auth, a standard error envelope, and a hand-written OpenAPI spec.

Domain logic stays in `knowledge/` — this module is pure transport. Kept
dependency-free (no flask-cors / openapi codegen) to match the project's
minimal-deps, no-LLM ethos. CORS itself is applied app-wide in `app.py`.
"""

import hmac
import io
import os
from datetime import date
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request, send_file

import observability
from knowledge import artifacts, schedule
from knowledge.copilot import PROFILES, CopilotError, build_copilot_prompt
from knowledge.lecture import LectureError, build_lecture_deck
from knowledge.materials import MaterialsError, build_materials

API_VERSION = "1.0.0"
MIN_DESCRIPTION_LENGTH = 15
MAX_DESCRIPTION_LENGTH = 5000
MIN_OBJECTIVES_LENGTH = 10
MAX_OBJECTIVES_LENGTH = 4000
MAX_TESTS = 12
MAX_TERM_LENGTH = 60
MIN_SCHEDULE_LENGTH = 15
MAX_SCHEDULE_LENGTH = 50000
MAX_FILENAME_LENGTH = 256
MAX_THEME_LENGTH = 300
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
PPTX_MIMETYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)

api = Blueprint("api", __name__)


# --- helpers -----------------------------------------------------------------


def error_response(code, message, status):
    """Every error, one shape: {"error": {"code", "message"}} + HTTP status."""
    return jsonify({"error": {"code": code, "message": message}}), status


def allowed_origin(request_origin):
    """Resolve the Access-Control-Allow-Origin value from CORS_ORIGINS.
    '*' (default) allows all; otherwise echo the request origin when it's in
    the configured comma-separated allowlist, else the first allowed origin."""
    configured = os.environ.get("CORS_ORIGINS", "*").strip()
    if configured == "*":
        return "*"
    allowed = [o.strip() for o in configured.split(",") if o.strip()]
    if request_origin and request_origin in allowed:
        return request_origin
    return allowed[0] if allowed else "*"


def require_api_key(view):
    """Gate a view behind API_KEY when that env var is set. Unset → open
    (local dev). Accepts `X-API-Key: <key>` or `Authorization: Bearer <key>`."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method == "OPTIONS":  # never gate CORS preflight
            return view(*args, **kwargs)
        expected = os.environ.get("API_KEY")
        if expected:
            provided = request.headers.get("X-API-Key", "")
            auth = request.headers.get("Authorization", "")
            if not provided and auth.startswith("Bearer "):
                provided = auth[7:]
            if not hmac.compare_digest(provided, expected):
                return error_response(
                    "unauthorized", "Missing or invalid API key.", 401
                )
        return view(*args, **kwargs)

    return wrapped


def _archive(kind, payload, content_type, metadata):
    """Best-effort: store a generated artifact on Vercel Blob and attach its URL
    to this request's access-log line. Never raises (storage must not affect the
    download)."""
    try:
        info = artifacts.store_artifact(
            kind, observability.current_request_id(), payload, content_type, metadata
        )
        observability.record_artifact(info)
    except Exception:
        current_app.logger.warning("artifact archiving failed", exc_info=True)


# --- OpenAPI spec ------------------------------------------------------------

SCHEDULE_EXAMPLE = {
    "description": (
        "An introductory college course in Python programming, covering "
        "variables, control flow, functions, and object-oriented programming."
    ),
    "weeks": 14,
    "startDate": "2026-08-24",
    "tests": 2,
    "term": "Fall 2026",
}

SCHEDULE_RESPONSE_EXAMPLE = {
    "subject": "Python",
    "confidence": "high",
    "term": "Fall 2026",
    "weeks": [
        {
            "week": 1,
            "dates": "Aug 24 – Aug 28",
            "topics": ["Introduction", "Variables"],
            "assignment": "Exercises: Introduction, Variables",
            "kind": "instruction",
        },
        {
            "week": 6,
            "dates": "Sep 28 – Oct 2",
            "topics": ["Review"],
            "assignment": "Review prior material and complete the practice set",
            "kind": "review",
        },
        {
            "week": 7,
            "dates": "Oct 5 – Oct 9",
            "topics": ["Exam"],
            "assignment": "Test",
            "kind": "exam",
        },
    ],
    "topics": [{"name": "Variables", "citations": [1], "position": 0.05}],
    "citations": [
        {
            "title": "Python Programming",
            "url": "https://en.wikiversity.org/wiki/Python_Programming",
            "source": "Wikiversity",
        }
    ],
}

LECTURE_EXAMPLE = {
    "title": "Introduction to Python",
    "objectives": (
        "By the end of this module, students will be able to define variables, "
        "explain control flow, and write functions."
    ),
}

COPILOT_EXAMPLE = {
    "schedule": (
        "Week,Dates,Topics,Assignment\n"
        '1,"Aug 17 – Aug 21","Variables",""\n'
        '2,"Aug 24 – Aug 28","Functions",""\n'
        '3,"Aug 31 – Sep 4","Review",""\n'
        '4,"Sep 7 – Sep 11","Midterm exam",""'
    ),
    "language": "python",
}

OPENAPI_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "Course Engine API",
        "version": API_VERSION,
        "description": (
            "LLM-free generation of college course schedules and teaching "
            "materials from trusted public curricula."
        ),
    },
    "servers": [{"url": "/"}],
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
        }
    },
    "paths": {
        "/api/v1/health": {
            "get": {
                "summary": "Liveness check",
                "security": [],
                "responses": {"200": {"description": "Service is up"}},
            }
        },
        "/api/v1/artifacts": {
            "get": {
                "summary": "List recently generated lectures/materials",
                "description": (
                    "Returns generated .pptx/.zip artifacts archived on Vercel Blob "
                    "(newest first), each with a download URL and its request "
                    "metadata. 'enabled' is false when Blob storage isn't configured."
                ),
                "security": [{"ApiKeyAuth": []}],
                "responses": {
                    "200": {
                        "description": "Stored artifacts",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "enabled": {"type": "boolean"},
                                        "artifacts": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "name": {"type": "string"},
                                                    "url": {"type": "string"},
                                                    "downloadUrl": {"type": "string"},
                                                    "size": {"type": "integer"},
                                                    "uploadedAt": {"type": "string"},
                                                    "metadata": {"type": "object"},
                                                },
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/api/v1/schedule": {
            "post": {
                "summary": "Generate a weekly topic schedule from a course description",
                "security": [{"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["description", "weeks"],
                                "properties": {
                                    "description": {
                                        "type": "string",
                                        "description": "Free-text course description.",
                                    },
                                    "weeks": {
                                        "type": "integer",
                                        "minimum": schedule.MIN_WEEKS,
                                        "maximum": schedule.MAX_WEEKS,
                                        "description": "Total weeks in the term. The schedule always returns exactly this many weeks.",
                                    },
                                    "startDate": {
                                        "type": "string",
                                        "format": "date",
                                        "description": "Optional. First day of instruction (ISO YYYY-MM-DD). When present, each week includes a Mon–Fri 'dates' range.",
                                    },
                                    "tests": {
                                        "type": "integer",
                                        "minimum": 0,
                                        "default": 0,
                                        "description": "Optional. Number of exams placed evenly across the term; each exam week is preceded by a review week, and both count toward the total weeks.",
                                    },
                                    "term": {
                                        "type": "string",
                                        "description": "Optional. Term label, e.g. 'Fall 2026', echoed back in the response.",
                                    },
                                },
                            },
                            "example": SCHEDULE_EXAMPLE,
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Weekly schedule",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "subject": {"type": "string"},
                                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                        "term": {"type": "string", "description": "Present only when supplied in the request."},
                                        "weeks": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "week": {"type": "integer"},
                                                    "topics": {"type": "array", "items": {"type": "string"}},
                                                    "dates": {
                                                        "type": "string",
                                                        "description": "Mon–Fri range, e.g. 'Aug 24 – Aug 28'. Present only when startDate was provided.",
                                                    },
                                                    "assignment": {
                                                        "type": "string",
                                                        "description": "Homework/activity for the week; 'Test' on exam weeks.",
                                                    },
                                                    "kind": {
                                                        "type": "string",
                                                        "enum": ["instruction", "review", "exam"],
                                                    },
                                                },
                                            },
                                        },
                                        "topics": {"type": "array", "items": {"type": "object"}},
                                        "citations": {"type": "array", "items": {"type": "object"}},
                                    },
                                },
                                "example": SCHEDULE_RESPONSE_EXAMPLE,
                            }
                        },
                    },
                    "400": {"description": "Invalid request"},
                    "422": {"description": "Could not identify a curriculum"},
                },
            }
        },
        "/api/v1/copilot-prompt": {
            "post": {
                "summary": "Stitch a schedule into a GitHub Copilot project prompt",
                "description": (
                    "Deterministically turns a course schedule (CSV or text) into a "
                    "ready-to-paste Copilot Agent-mode prompt that scaffolds a full "
                    "student project. Makes no upstream calls — always fast, no LLM."
                ),
                "security": [{"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["schedule"],
                                "properties": {
                                    "schedule": {
                                        "type": "string",
                                        "description": "Raw CSV or text of the weekly schedule (Week, Dates, Topics, Assignment).",
                                    },
                                    "fileName": {
                                        "type": "string",
                                        "description": "Optional. Extra signal for language inference.",
                                    },
                                    "language": {
                                        "type": "string",
                                        "enum": sorted(PROFILES),
                                        "description": "Optional. Override the inferred course language.",
                                    },
                                    "projectTheme": {
                                        "type": "string",
                                        "description": "Optional. Override the inferred project theme.",
                                    },
                                },
                            },
                            "example": COPILOT_EXAMPLE,
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "The Copilot prompt",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "prompt": {"type": "string"},
                                        "language": {"type": "string"},
                                        "weeks": {"type": "integer"},
                                    },
                                }
                            }
                        },
                    },
                    "400": {"description": "Invalid or unparseable schedule"},
                },
            }
        },
        "/api/v1/lecture": {
            "post": {
                "summary": "Generate a PowerPoint lecture from module objectives",
                "description": (
                    "Returns a .pptx: per objective, an explanation slide plus "
                    "worked-example slide(s) with talking points in speaker notes."
                ),
                "security": [{"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["objectives"],
                                "properties": {
                                    "objectives": {
                                        "type": "string",
                                        "description": "Free-form objectives (list or prose).",
                                    },
                                    "title": {"type": "string"},
                                },
                            },
                            "example": LECTURE_EXAMPLE,
                        }
                    },
                },
                "responses": {
                    "200": {"description": "module-lecture.pptx (PowerPoint)"},
                    "400": {"description": "Invalid request"},
                    "422": {"description": "No objectives could be parsed"},
                },
            }
        },
        "/api/v1/materials": {
            "post": {
                "summary": "Generate course materials from a project zip",
                "description": (
                    "Returns a zip of PPTX lectures, DOCX LMS intros and "
                    "assignments, and a deterministic rubric.csv."
                ),
                "security": [{"ApiKeyAuth": []}],
                "requestBody": {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "project": {"type": "string", "format": "binary"}
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "course-materials.zip (application/zip)"},
                    "422": {"description": "Project structure not recognized"},
                },
            }
        },
    },
}


# --- routes ------------------------------------------------------------------


@api.get("/api/v1/health")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "course-engine",
            "version": API_VERSION,
            "endpoints": sorted(OPENAPI_SPEC["paths"]),
        }
    )


@api.get("/api/v1/openapi.json")
def openapi():
    return jsonify(OPENAPI_SPEC)


@api.get("/api/v1/artifacts")
@require_api_key
def list_artifacts():
    """Recent generated lectures/materials stored on Vercel Blob, newest first.
    'enabled' is false when Blob storage isn't configured (e.g. local dev)."""
    return jsonify({"enabled": artifacts.enabled(), "artifacts": artifacts.list_artifacts()})


@api.route("/api/v1/schedule", methods=["POST"])
@api.route("/api/schedule", methods=["POST"])  # deprecated alias
@require_api_key
def make_schedule():
    data = request.get_json(silent=True) or {}
    description = (data.get("description") or "").strip()
    weeks = data.get("weeks")

    if len(description) < MIN_DESCRIPTION_LENGTH:
        return error_response("invalid_request", "Please provide a course description.", 400)
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return error_response(
            "invalid_request",
            f"Description too long (max {MAX_DESCRIPTION_LENGTH} chars).",
            400,
        )
    try:
        weeks = int(weeks)
    except (TypeError, ValueError):
        return error_response("invalid_request", "Number of weeks must be a whole number.", 400)
    if not schedule.MIN_WEEKS <= weeks <= schedule.MAX_WEEKS:
        return error_response(
            "invalid_request",
            f"Weeks must be between {schedule.MIN_WEEKS} and {schedule.MAX_WEEKS}.",
            400,
        )

    # Optional scheduling controls (backward compatible — absent => today's behavior).
    start_date = None
    raw_start = data.get("startDate")
    if raw_start not in (None, ""):
        if not isinstance(raw_start, str):
            return error_response("invalid_request", "startDate must be an ISO date string (YYYY-MM-DD).", 400)
        try:
            start_date = date.fromisoformat(raw_start)
        except ValueError:
            return error_response("invalid_request", "startDate must be a valid ISO date (YYYY-MM-DD).", 400)

    raw_tests = data.get("tests", 0)
    try:
        tests = int(raw_tests) if raw_tests not in (None, "") else 0
    except (TypeError, ValueError):
        return error_response("invalid_request", "tests must be a non-negative integer.", 400)
    if tests < 0 or tests > MAX_TESTS:
        return error_response("invalid_request", f"tests must be between 0 and {MAX_TESTS}.", 400)

    term = data.get("term")
    if term is not None and not isinstance(term, str):
        return error_response("invalid_request", "term must be a string.", 400)
    term = (term or "").strip()
    if len(term) > MAX_TERM_LENGTH:
        return error_response("invalid_request", f"term too long (max {MAX_TERM_LENGTH} chars).", 400)

    try:
        result = schedule.build_schedule(
            description, weeks, start_date=start_date, tests=tests, term=term or None
        )
    except Exception:
        current_app.logger.exception("schedule failure")
        return error_response("internal_error", "Something went wrong while building the schedule.", 500)
    if "error" in result:
        return error_response("no_curriculum", result["error"], 422)
    return jsonify(result)


@api.route("/api/v1/copilot-prompt", methods=["POST"])
@api.route("/api/copilot-prompt", methods=["POST"])  # deprecated alias
@require_api_key
def make_copilot_prompt():
    data = request.get_json(silent=True) or {}
    schedule_text = data.get("schedule")
    if not isinstance(schedule_text, str) or not schedule_text.strip():
        return error_response("invalid_request", "Field 'schedule' is required.", 400)
    schedule_text = schedule_text.strip()
    if not MIN_SCHEDULE_LENGTH <= len(schedule_text) <= MAX_SCHEDULE_LENGTH:
        return error_response(
            "invalid_request",
            f"'schedule' must be {MIN_SCHEDULE_LENGTH}–{MAX_SCHEDULE_LENGTH} characters.",
            400,
        )

    file_name = data.get("fileName")
    if file_name is not None and (not isinstance(file_name, str) or len(file_name) > MAX_FILENAME_LENGTH):
        return error_response("invalid_request", f"'fileName' must be a string ≤ {MAX_FILENAME_LENGTH} chars.", 400)

    language = data.get("language")
    if language is not None and language not in PROFILES:
        return error_response("invalid_request", f"'language' must be one of {sorted(PROFILES)}.", 400)

    project_theme = data.get("projectTheme")
    if project_theme is not None and (not isinstance(project_theme, str) or len(project_theme) > MAX_THEME_LENGTH):
        return error_response("invalid_request", f"'projectTheme' must be a string ≤ {MAX_THEME_LENGTH} chars.", 400)

    try:
        result = build_copilot_prompt(schedule_text, file_name, language, project_theme)
    except CopilotError as error:
        return error_response("invalid_request", str(error), 400)
    except Exception:
        current_app.logger.exception("copilot-prompt generation failed")
        return error_response("internal_error", "Something went wrong while building the prompt.", 500)
    return jsonify(result)


@api.route("/api/v1/lecture", methods=["POST"])
@require_api_key
def make_lecture():
    data = request.get_json(silent=True) or {}
    objectives = data.get("objectives")
    if isinstance(objectives, list):
        objectives = "\n".join(str(item) for item in objectives)
    objectives = (objectives or "").strip()
    title = (data.get("title") or "Module Lecture").strip()

    if len(objectives) < MIN_OBJECTIVES_LENGTH:
        return error_response("invalid_request", "Provide the module's learning objectives.", 400)
    if len(objectives) > MAX_OBJECTIVES_LENGTH:
        return error_response(
            "invalid_request",
            f"Objectives too long (max {MAX_OBJECTIVES_LENGTH} chars).",
            400,
        )

    try:
        payload, summary = build_lecture_deck(objectives, title)
    except LectureError as error:
        return error_response("invalid_request", str(error), 422)
    except Exception:
        current_app.logger.exception("lecture generation failed")
        return error_response("internal_error", "Something went wrong while building the lecture.", 500)
    current_app.logger.info("lecture generated: %s objectives", summary["objectives"])
    _archive(
        "lecture",
        payload,
        PPTX_MIMETYPE,
        {"title": title, "objectives": objectives[:1000], "summary": summary},
    )
    return send_file(
        io.BytesIO(payload),
        mimetype=PPTX_MIMETYPE,
        as_attachment=True,
        download_name="module-lecture.pptx",
    )


@api.route("/api/v1/materials", methods=["POST"])
@api.route("/api/materials", methods=["POST"])  # deprecated alias
@require_api_key
def make_materials():
    upload = request.files.get("project")
    if upload is None or not upload.filename:
        return error_response("invalid_request", "Upload the generated project as a .zip file.", 400)
    data = upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        return error_response(
            "payload_too_large", f"Zip too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).", 413
        )
    try:
        payload, summary = build_materials(data)
    except MaterialsError as error:
        return error_response("invalid_project", str(error), 422)
    except Exception:
        current_app.logger.exception("materials generation failed")
        return error_response("internal_error", "Something went wrong while generating materials.", 500)
    current_app.logger.info("materials generated: %s units", summary["units"])
    _archive(
        "materials",
        payload,
        "application/zip",
        {"filename": upload.filename, "summary": summary},
    )
    return send_file(
        io.BytesIO(payload),
        mimetype="application/zip",
        as_attachment=True,
        download_name="course-materials.zip",
    )
