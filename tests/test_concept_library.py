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
