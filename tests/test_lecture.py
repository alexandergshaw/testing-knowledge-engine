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
from knowledge.slides import slide_title
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


def test_programming_lecture_defers_to_concept_examples():
    # In a programming lecture, per-objective examples are empty — concepts drive
    # the example slides instead (see _attach_concept_examples).
    query = analyze("How do Python loops work?")
    passage = make_passage(source="Stack Overflow", code=["for i in range(3):\n    print(i)"])
    assert extract_examples(query, [passage], [], programming_lecture=True) == []


# --- concept extraction & per-concept code ----------------------------------


def test_extract_concepts_ordered_and_deduped():
    from knowledge.lecture import extract_concepts

    concepts = extract_concepts(analyze("Explain conditionals and loops, and write functions"))
    assert concepts == ["Conditionals", "Loops", "Functions"]
    # synonyms collapse to the canonical name
    assert extract_concepts(analyze("Use lists and arrays")) == ["Lists & Arrays"]
    # a conceptual / language-only objective names no concept
    assert extract_concepts(analyze("Explain the history of Python")) == []


def test_extract_concepts_multiword_phrases():
    from knowledge.lecture import extract_concepts

    assert extract_concepts(analyze("Implement basic control structures")) == ["Control Structures"]
    assert extract_concepts(analyze("Choose appropriate numeric data types")) == ["Data Types"]
    assert extract_concepts(analyze("Explain common data structures")) == ["Data Structures"]
    # genuinely conceptual objectives still name no concept (no code slide)
    assert extract_concepts(analyze("Describe problem-solving strategies")) == []
    assert extract_concepts(analyze("Provide examples of computer science")) == []


def test_parse_recognizes_choose_and_provide_verbs():
    # "Choose"/"Provide" must start their own objectives, not merge into the prior.
    objs = parse_objectives(
        "Provide examples of CS. Choose numeric data types. Implement control structures."
    )
    assert objs == [
        "Provide examples of CS",
        "Choose numeric data types",
        "Implement control structures",
    ]


def test_concept_code_forces_stackoverflow_retrieval(monkeypatch):
    # A concept search string ("Data Types example") doesn't trip is_programming,
    # so _concept_code must force it so Stack Overflow (the code source) is queried.
    import knowledge.lecture as lecture

    captured = {}

    def fake_select(query):
        captured["is_programming"] = query.is_programming
        return []

    monkeypatch.setattr(lecture, "select_sources", fake_select)
    monkeypatch.setattr(lecture, "fetch", lambda query, sources: [])
    lecture._concept_code("Data Types", "uniquelang-xyz")  # fresh cache key
    assert captured["is_programming"] is True


def test_infer_language_from_title_and_objectives():
    from knowledge.lecture import _infer_language

    assert _infer_language(["write a for loop"], "Introduction to Python") == "Python"
    assert _infer_language(["write JavaScript functions"], "Web Dev") == "JavaScript"
    assert _infer_language(["explain cognitive dissonance"], "Psychology") == ""


def test_concept_code_caches_and_captions(monkeypatch):
    import knowledge.lecture as lecture

    calls = {"n": 0}

    def fake_fetch(query, sources):
        calls["n"] += 1
        return [make_passage(source="Stack Overflow", code=["for i in range(3):\n    print(i)"])]

    monkeypatch.setattr(lecture, "fetch", fake_fetch)
    monkeypatch.setattr(lecture, "select_sources", lambda q: [])
    monkeypatch.setattr(
        lecture, "rank",
        lambda q, passages: [
            ScoredSentence(text="For example, a loop repeats a block.", tokens=[], passage=passages[0], score=5.0)
        ],
    )

    example = lecture._concept_code("Loops", "Python")
    assert example["kind"] == "code" and example["concept"] == "Loops"
    assert example["lines"][0] == "for i in range(3):"
    assert "loop" in example["text"].lower()
    lecture._concept_code("Loops", "Python")  # cached -> no second fetch
    assert calls["n"] == 1


def test_attach_concept_examples_one_unit_per_concept():
    import knowledge.lecture as lecture

    # Conditionals/Loops/Functions are all curated, so units come from the
    # library (no network), de-duplicated and attached to the first owner.
    results = [
        lecture.ObjectiveResult(objective="Explain conditionals and loops"),
        lecture.ObjectiveResult(objective="Write functions and more loops"),  # 'loops' dup
    ]
    lecture._attach_concept_examples(results, [r.objective for r in results], "Intro to Python")
    concepts = [unit["concept"] for r in results for unit in r.concept_examples]
    assert concepts == ["Conditionals", "Loops", "Functions"]  # deduped, ordered
    # Each unit is the full 4-part shape.
    for r in results:
        for unit in r.concept_examples:
            assert set(unit) >= {"example", "walkthrough", "practice", "answer"}
    # 'Loops' attached to the FIRST objective that named it
    assert any(unit["concept"] == "Loops" for unit in results[0].concept_examples)
    assert all(unit["concept"] != "Loops" for unit in results[1].concept_examples)


def test_concept_unit_fallback_builds_deterministic_unit(monkeypatch):
    import knowledge.lecture as lecture

    # An uncurated concept: retrieval supplies the example; the rest is derived.
    monkeypatch.setattr(
        lecture,
        "_concept_code",
        lambda concept, language: {
            "kind": "code",
            "concept": concept,
            "text": "A worked example.",
            "lines": ["x = 1", "for i in range(x):", "    print(i)"],
            "title": concept,
            "url": "u",
            "source": "Stack Overflow",
        },
    )
    unit = lecture._concept_unit("Generators", "Python")
    assert unit["example"]["lines"][0] == "x = 1"
    assert len(unit["walkthrough"]) == 3                 # one line described per code line
    assert any("Assigns a value to x" in b for b in unit["walkthrough"])
    assert any("loop" in b.lower() for b in unit["walkthrough"])
    assert unit["practice"] and "Recreate" in unit["practice"][0]


def test_describe_line_recognizes_common_shapes():
    from knowledge.lecture import _describe_line

    assert _describe_line("def greet(name):").startswith("Defines the function greet")
    assert _describe_line("class Dog:").startswith("Defines the class Dog")
    assert "loop" in _describe_line("for i in range(3):").lower()
    assert _describe_line("total = 5 + 2").startswith("Assigns a value to total")
    assert _describe_line("return total").startswith("Returns")
    assert _describe_line("") is None


def test_is_programming_lecture_detection():
    from knowledge.lecture import is_programming_lecture

    assert is_programming_lecture(["write a Python for loop", "define a function"])
    assert is_programming_lecture(["explain the history of it"], title="Introduction to Python")
    assert not is_programming_lecture(
        ["explain operant conditioning", "describe classical conditioning"]
    )


def _slide_code(slide):
    """The monospace code lines on a slide built by these helpers."""
    for shape in slide.shapes:
        if shape.has_text_frame and any(
            p.font.name == "Courier New" for p in shape.text_frame.paragraphs
        ):
            return [p.text for p in shape.text_frame.paragraphs]
    return []


def _unit_example():
    return {
        "concept": "Loops",
        "language": "Python",
        "example": {
            "caption": "For example, this loop prints 0, 1, 2.",
            "lines": ["for i in range(3):", "    print(i)"],
        },
        "walkthrough": ["range(3) yields 0, 1, 2.", "print runs once per value."],
        "practice": ["Print the numbers 0 to 4 with a loop."],
        "answer": {"caption": "Looping to five.", "lines": ["for i in range(5):", "    print(i)"]},
        "title": "",
        "url": "",
        "source": "Curated",
    }


def test_concept_unit_renders_four_slides_in_order():
    from pptx import Presentation

    results = [
        ObjectiveResult(
            objective="Explain loops",
            points=["A loop repeats code."],
            concept_examples=[_unit_example()],
            citations=[],
            confidence="high",
        )
    ]
    deck = Presentation(io.BytesIO(build_module_deck("Intro to Python", results)))
    titles = [slide_title(s) for s in deck.slides]
    unit_titles = [t for t in titles if t.split(":")[0] in ("Example", "Walkthrough", "Practice", "Answer")]
    # The fixed unit, immediately consecutive and in order.
    assert unit_titles == ["Example: Loops", "Walkthrough: Loops", "Practice: Loops", "Answer: Loops"]


def test_concept_example_slide_renders_words_and_code():
    from pptx import Presentation

    deck = Presentation(io.BytesIO(build_module_deck("Intro to Python", [
        ObjectiveResult(objective="Explain loops", points=["A loop repeats code."],
                        concept_examples=[_unit_example()], citations=[], confidence="high")
    ])))
    slide = next(s for s in deck.slides if slide_title(s) == "Example: Loops")
    text = "\n".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)
    assert "this loop prints" in text                       # words
    assert "for i in range(3):" in text                     # code
    assert _slide_code(slide)                                # rendered in monospace


def test_practice_code_is_example_reference_not_the_answer():
    # Spec §4: walkthrough and practice both show the EXAMPLE snippet verbatim;
    # only the answer carries its own distinct solution.
    from pptx import Presentation

    deck = Presentation(io.BytesIO(build_module_deck("Intro to Python", [
        ObjectiveResult(objective="Explain loops", points=["A loop repeats code."],
                        concept_examples=[_unit_example()], citations=[], confidence="high")
    ])))
    by_title = {slide_title(s): s for s in deck.slides}
    example_code = _slide_code(by_title["Example: Loops"])
    assert _slide_code(by_title["Walkthrough: Loops"]) == example_code
    assert _slide_code(by_title["Practice: Loops"]) == example_code
    # The answer must NOT be the reference snippet.
    assert _slide_code(by_title["Answer: Loops"]) != example_code


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
                    "text": "For example, this loop prints 0, 1, 2.",
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
    titles = [slide_title(s) for s in deck.slides]
    # title, overview, obj1 explanation, obj1 example, obj2 explanation, obj2 example, references
    assert len(deck.slides) == 7
    assert any("Intro to Python" in t for t in titles)
    assert "Variables" in titles and "Loops" in titles  # clean topic titles, no "Objective N:"
    assert sum(t.startswith("Example") for t in titles) == 2
    assert "References" in titles


def test_deck_examples_have_speaker_notes():
    deck = build_two_objective_deck()
    notes = [
        s.notes_slide.notes_text_frame.text for s in deck.slides if s.has_notes_slide
    ]
    assert any("Talking points" in n for n in notes)
    assert any("Source:" in n for n in notes)


def test_code_example_slide_has_words_and_code():
    deck = build_two_objective_deck()
    example_slide = next(
        s for s in deck.slides
        if any(sh.has_text_frame and "loop prints" in sh.text_frame.text for sh in s.shapes)
    )
    text = "\n".join(sh.text_frame.text for sh in example_slide.shapes if sh.has_text_frame)
    assert "For example, this loop prints" in text          # words
    assert "for i in range(3):" in text                     # code
    # the code lives in a monospace box
    monospace = any(
        sh.has_text_frame
        and any(p.font.name == "Courier New" for p in sh.text_frame.paragraphs)
        for sh in example_slide.shapes
    )
    assert monospace


def test_deck_references_number_unique_sources():
    deck = build_two_objective_deck()
    references = next(s for s in deck.slides if slide_title(s) == "References")
    body = "\n".join(
        shape.text_frame.text for shape in references.shapes if shape.has_text_frame
    )
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
