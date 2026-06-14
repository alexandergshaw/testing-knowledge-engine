from knowledge import concept_library
from knowledge.lecture import _curated_explanation
from knowledge.synthesize import sanitize_layman


def test_library_explanation_and_code():
    bullets = concept_library.explanation_for("Functions")
    assert bullets and any("recipe" in b.lower() for b in bullets)

    code = concept_library.code_for("Functions", "Python")
    assert code["language"] == "Python"
    assert any("def apply_discount" in line for line in code["lines"])
    assert code["caption"]


def test_conceptual_topic_has_explanation_but_no_code():
    assert concept_library.explanation_for("Problem-Solving Strategies")
    assert concept_library.code_for("Problem-Solving Strategies") is None


def test_unit_for_returns_full_distinct_unit():
    unit = concept_library.unit_for("Data Types", "Python")
    assert unit["language"] == "Python"
    assert unit["example"]["lines"] and unit["example"]["caption"]
    assert len(unit["walkthrough"]) >= 2          # line-by-line explanation
    assert 1 <= len(unit["practice"]) <= 2        # the challenge
    assert unit["answer"]["lines"] and unit["answer"]["caption"]
    # Spec §4: the answer must be a DISTINCT solution, not the reference snippet.
    assert unit["answer"]["lines"] != unit["example"]["lines"]


def test_unit_for_curated_concepts_are_all_complete():
    # Every programming concept that ships curated code ships a full, distinct unit.
    for name, entry in concept_library.LIBRARY.items():
        if "code" not in entry:
            continue
        unit = concept_library.unit_for(name)
        assert unit is not None, name
        assert unit["walkthrough"] and unit["practice"]
        assert unit["answer"]["lines"] != unit["example"]["lines"], name


def test_unit_for_missing_concept_is_none():
    assert concept_library.unit_for("Problem-Solving Strategies") is None
    assert concept_library.unit_for("Nonexistent Concept") is None


def test_match_topic():
    assert (
        concept_library.match_topic("Provide examples of computer science in the real world")
        == "Computer Science in the Real World"
    )
    assert concept_library.match_topic("Describe problem-solving strategies") == "Problem-Solving Strategies"
    assert concept_library.match_topic("Explain cognitive dissonance") is None


def test_curated_explanation_covers_concepts_and_topics():
    # The user's objectives — all curated (concepts + intro-CS topics).
    assert _curated_explanation("Choose appropriate numeric data types") is not None
    assert _curated_explanation("Organize computer programs using functions") is not None
    assert _curated_explanation("Implement basic control structures") is not None
    assert _curated_explanation("Provide examples of Computer Science in the Real World") is not None
    assert _curated_explanation("Describe Problem-solving strategies") is not None
    # not curated -> falls back to retrieval
    assert _curated_explanation("Explain cognitive dissonance") is None


def test_sanitize_layman_strips_latex_and_markup():
    dirty = r"It runs in O ( n ) {\displaystyle O(n)} time and O ( 1 ) {\displaystyle O(1)} space."
    clean = sanitize_layman(dirty)
    assert "displaystyle" not in clean and "{" not in clean and "}" not in clean
    assert "(n)" in clean and "(1)" in clean and clean.startswith("It runs in")
