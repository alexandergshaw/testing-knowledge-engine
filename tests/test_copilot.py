import pytest

import app as app_module
from knowledge.copilot import (
    CopilotError,
    build_copilot_prompt,
    classify,
    infer_language,
    parse_schedule,
)

CSV_SCHEDULE = (
    "Week,Dates,Topics,Assignment\n"
    '1,"Aug 17 – Aug 21","Variables",""\n'
    '2,"Aug 24 – Aug 28","Relational databases and queries",""\n'
    '3,"Aug 31 – Sep 4","Review",""\n'
    '4,"Sep 7 – Sep 11","Final assessment",""'
)


# --- parsing -----------------------------------------------------------------


def test_parse_csv_with_header_and_quoted_fields():
    rows = parse_schedule(CSV_SCHEDULE)
    assert [r["week"] for r in rows] == [1, 2, 3, 4]
    assert rows[0]["topics"] == "Variables"
    assert rows[1]["topics"] == "Relational databases and queries"
    assert rows[0]["dates"] == "Aug 17 – Aug 21"


def test_parse_line_based_fallback():
    rows = parse_schedule("Variables\nLoops\nFunctions")
    assert [r["topics"] for r in rows] == ["Variables", "Loops", "Functions"]
    assert [r["week"] for r in rows] == [1, 2, 3]


def test_parse_skips_blank_rows():
    rows = parse_schedule("Week,Topics\n1,Variables\n\n2,Loops")
    assert [r["topics"] for r in rows] == ["Variables", "Loops"]


# --- classification ----------------------------------------------------------


def test_classify_exam_review_instructional():
    assert classify({"topics": "Final exam", "assignment": ""}) == "exam"
    assert classify({"topics": "Review", "assignment": ""}) == "review"
    assert classify({"topics": "Variables", "assignment": "Homework"}) == "instructional"


def test_classify_exam_beats_review():
    # "Exam Review" / "Review and final assessment" count as exam.
    assert classify({"topics": "Exam Review", "assignment": ""}) == "exam"
    assert classify({"topics": "Review and final assessment", "assignment": ""}) == "exam"


# --- language inference ------------------------------------------------------


def test_infer_language_picks_sql_for_database_course():
    rows = parse_schedule(CSV_SCHEDULE)
    assert infer_language(rows, "databases_schedule.csv", None) == "sql"


def test_infer_language_override_wins():
    rows = parse_schedule(CSV_SCHEDULE)
    assert infer_language(rows, "databases.csv", "python") == "python"


def test_infer_language_defaults_to_javascript():
    rows = parse_schedule("Week,Topics\n1,Generic topic without signals")
    assert infer_language(rows, None, None) == "javascript"


# --- prompt building ---------------------------------------------------------


def test_build_prompt_is_deterministic():
    a = build_copilot_prompt(CSV_SCHEDULE)
    b = build_copilot_prompt(CSV_SCHEDULE)
    assert a["prompt"] == b["prompt"]  # byte-identical


def test_build_prompt_structure_and_folders():
    result = build_copilot_prompt(CSV_SCHEDULE, language="python")
    prompt = result["prompt"]
    assert result["language"] == "python"
    assert result["weeks"] == 4
    # Onboarding + per-week folders by kind.
    assert "- assignment0: Onboarding" in prompt
    assert "assignment1 - Topic: Variables" in prompt
    assert "assignment2 - Topic: Relational databases and queries" in prompt
    assert "review1 - Review of: Review" in prompt
    assert "exam1 - Assessment: Final assessment" in prompt
    # Core rules + language-specific filenames present.
    assert 'name it `solution.py`' in prompt
    assert "test_solution.py" in prompt
    assert 'root-level "assignments/" directory' in prompt
    assert "deployed to Vercel" in prompt
    assert "4-week term" in prompt


def test_project_theme_override():
    result = build_copilot_prompt(CSV_SCHEDULE, project_theme="a custom capstone")
    assert "The project is a custom capstone," in result["prompt"]


def test_empty_schedule_raises():
    with pytest.raises(CopilotError):
        build_copilot_prompt("   ")


# --- API route ---------------------------------------------------------------


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_route_happy_path(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    res = client.post("/api/v1/copilot-prompt", json={"schedule": CSV_SCHEDULE})
    assert res.status_code == 200
    body = res.get_json()
    assert body["prompt"].startswith("Build a complete")
    assert body["weeks"] == 4


def test_route_byte_identical(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    one = client.post("/api/v1/copilot-prompt", json={"schedule": CSV_SCHEDULE}).get_json()
    two = client.post("/api/v1/copilot-prompt", json={"schedule": CSV_SCHEDULE}).get_json()
    assert one["prompt"] == two["prompt"]


def test_route_alias_works(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    assert client.post("/api/copilot-prompt", json={"schedule": CSV_SCHEDULE}).status_code == 200


def test_route_rejects_missing_and_short_schedule(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    assert client.post("/api/v1/copilot-prompt", json={}).status_code == 400
    short = client.post("/api/v1/copilot-prompt", json={"schedule": "tiny"})
    assert short.status_code == 400
    assert short.get_json()["error"]["code"] == "invalid_request"


def test_route_rejects_bad_language(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    res = client.post("/api/v1/copilot-prompt", json={"schedule": CSV_SCHEDULE, "language": "cobol"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_request"


def test_route_auth_enforced(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    assert client.post("/api/v1/copilot-prompt", json={"schedule": CSV_SCHEDULE}).status_code == 401
    ok = client.post(
        "/api/v1/copilot-prompt", json={"schedule": CSV_SCHEDULE}, headers={"X-API-Key": "secret"}
    )
    assert ok.status_code == 200


def test_appears_in_health_and_openapi(client):
    assert "/api/v1/copilot-prompt" in client.get("/api/v1/health").get_json()["endpoints"]
    spec = client.get("/api/v1/openapi.json").get_json()
    assert "/api/v1/copilot-prompt" in spec["paths"]
