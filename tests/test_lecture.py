import io

import pytest
from pptx import Presentation

import app as app_module
import service as service_module
from knowledge.lecture import (
    ObjectiveResult,
    build_module_deck,
    extract_examples,
    parse_objectives,
)
from knowledge.query import analyze
from knowledge.ranking import ScoredSentence
from knowledge.sources.base import Passage
from service import PPTX_MIMETYPE


# --- parse_objectives: format-agnostic --------------------------------------


def test_parse_lead_in_prose():
    objectives = parse_objectives(
        "By the end of this module, students will be able to define variables, "
        "explain control flow, and write functions."
    )
    assert objectives == ["define variables", "explain control flow", "write functions"]


def test_parse_inline_numbered_list():
    objectives = parse_objectives("1. Define variables 2. Explain loops 3. Write functions")
    assert objectives == ["Define variables", "Explain loops", "Write functions"]


def test_parse_inline_bullets():
    objectives = parse_objectives("- Define variables - Explain loops - Write functions")
    assert objectives == ["Define variables", "Explain loops", "Write functions"]


def test_parse_run_on_action_verbs():
    objectives = parse_objectives(
        "Define variables. Explain control flow. Apply reinforcement schedules."
    )
    assert objectives == [
        "Define variables",
        "Explain control flow",
        "Apply reinforcement schedules",
    ]


def test_parse_single_objective():
    text = "Understand the fundamentals of cognitive dissonance theory"
    assert parse_objectives(text) == [text]


def test_parse_does_not_truncate_outcomes_objective():
    # "outcomes" is a lead-in word only as a colon header — not mid-objective.
    objectives = parse_objectives(
        "Evaluate learning outcomes; design assessment rubrics"
    )
    assert objectives == ["Evaluate learning outcomes", "design assessment rubrics"]


def test_parse_caps_and_dedupes():
    objectives = parse_objectives("define x; define x; explain y")
    assert objectives == ["define x", "explain y"]


# --- extract_examples --------------------------------------------------------


def make_passage(text="An explanation.", title="T", source="Wikipedia", code=None):
    return Passage(text=text, title=title, url="http://x", source=source, trust=1.0, code=code or [])


def test_extract_code_example_for_programming():
    query = analyze("How do Python loops work?")
    assert query.is_programming
    passage = make_passage(source="Stack Overflow", code=["for i in range(3):\n    print(i)"])
    examples = extract_examples(query, [passage], [])
    assert examples[0]["kind"] == "code"
    assert examples[0]["lines"][0] == "for i in range(3):"
    assert examples[0]["lines"][1] == "    print(i)"


def test_extract_prose_example_by_marker():
    query = analyze("What is cognitive dissonance?")
    passage = make_passage()
    marked = ScoredSentence(
        text="For example, a smoker who knows smoking is harmful feels discomfort.",
        tokens=[],
        passage=passage,
        score=5.0,
    )
    plain = ScoredSentence(text="It is mental discomfort.", tokens=[], passage=passage, score=4.0)
    examples = extract_examples(query, [passage], [marked, plain])
    assert examples[0]["kind"] == "prose"
    assert "For example" in examples[0]["text"]


def test_extract_falls_back_to_top_sentence():
    query = analyze("What is entropy?")
    passage = make_passage()
    plain = ScoredSentence(
        text="Entropy measures disorder in a system over time.",
        tokens=[],
        passage=passage,
        score=3.0,
    )
    examples = extract_examples(query, [passage], [plain])
    assert examples[0]["fallback"] is True


# --- deck assembly -----------------------------------------------------------


def build_two_objective_deck():
    results = [
        ObjectiveResult(
            objective="Define variables",
            points=["A variable stores data.", "Variables have names."],
            examples=[
                {
                    "kind": "prose",
                    "text": "For example, x = 5 binds x to 5.",
                    "title": "Variable",
                    "url": "http://v",
                    "source": "Wikipedia",
                }
            ],
            citations=[{"title": "Variable", "url": "http://v", "source": "Wikipedia"}],
            confidence="high",
        ),
        ObjectiveResult(
            objective="Write loops",
            points=["A loop repeats code."],
            examples=[
                {
                    "kind": "code",
                    "lines": ["for i in range(3):", "    print(i)"],
                    "title": "Loops",
                    "url": "http://l",
                    "source": "Stack Overflow",
                }
            ],
            citations=[],
            confidence="medium",
        ),
    ]
    return Presentation(io.BytesIO(build_module_deck("Intro to Python", results)))


def test_deck_structure_and_notes():
    deck = build_two_objective_deck()
    titles = [s.shapes.title.text for s in deck.slides if s.shapes.title]
    # title, agenda, obj1 explanation, obj1 example, obj2 explanation, obj2 example, references
    assert len(deck.slides) == 7
    assert any("Intro to Python" in t for t in titles)
    assert any(t.startswith("Objective 1") for t in titles)
    assert sum(t.startswith("Example") for t in titles) == 2
    assert "References" in titles


def test_deck_examples_have_speaker_notes():
    deck = build_two_objective_deck()
    notes = [
        s.notes_slide.notes_text_frame.text for s in deck.slides if s.has_notes_slide
    ]
    assert any("Talking points" in n for n in notes)
    assert any("Source:" in n for n in notes)


def test_deck_references_number_unique_sources():
    deck = build_two_objective_deck()
    references = next(
        s for s in deck.slides if s.shapes.title and s.shapes.title.text == "References"
    )
    body = references.placeholders[1].text_frame.text
    assert "Variable" in body and "Loops" in body


# --- API route ---------------------------------------------------------------


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_lecture_route_serves_pptx(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.setattr(
        service_module,
        "build_lecture_deck",
        lambda objectives, title: (b"PK\x03\x04fakepptx", {"objectives": 2, "title": title, "items": []}),
    )
    res = client.post(
        "/api/v1/lecture",
        json={"objectives": "define variables. explain loops.", "title": "T"},
    )
    assert res.status_code == 200
    assert res.mimetype == PPTX_MIMETYPE
    assert res.data == b"PK\x03\x04fakepptx"


def test_lecture_route_accepts_list(client, monkeypatch):
    captured = {}
    monkeypatch.delenv("API_KEY", raising=False)

    def fake(objectives, title):
        captured["objectives"] = objectives
        return (b"x", {"objectives": 2, "title": title, "items": []})

    monkeypatch.setattr(service_module, "build_lecture_deck", fake)
    client.post("/api/v1/lecture", json={"objectives": ["define x", "explain y"]})
    assert "define x" in captured["objectives"] and "explain y" in captured["objectives"]


def test_lecture_route_validates_length(client, monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    res = client.post("/api/v1/lecture", json={"objectives": "short"})
    assert res.status_code == 400
    assert res.get_json()["error"]["code"] == "invalid_request"


def test_lecture_in_openapi(client):
    spec = client.get("/api/v1/openapi.json").get_json()
    assert "/api/v1/lecture" in spec["paths"]
    assert spec["paths"]["/api/v1/lecture"]["post"]["security"] == [{"ApiKeyAuth": []}]
