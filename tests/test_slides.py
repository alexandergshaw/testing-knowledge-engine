import io

from pptx import Presentation

from knowledge.lecture import ObjectiveResult, build_module_deck
from knowledge.slides import (
    MAX_BULLETS,
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    add_bullet_slide,
    clean_bullet,
    clean_title,
    new_deck,
)


# --- text normalization ------------------------------------------------------


def test_clean_title_title_cases_and_preserves_acronyms():
    assert (
        clean_title("objective 1: explain what a python variable is")
        == "Objective 1: Explain What a Python Variable Is"
    )
    assert clean_title("intro to HTML and CSS") == "Intro to HTML and CSS"
    assert clean_title("Variables, I/O, Branching.") == "Variables, I/O, Branching"


def test_clean_bullet_makes_self_contained():
    assert clean_bullet("[1] the mental discomfort felt") == "The mental discomfort felt."
    assert clean_bullet("- run the tests!") == "Run the tests!"
    assert clean_bullet("   ") == ""


# --- slide invariants --------------------------------------------------------


def test_new_deck_is_widescreen():
    deck = new_deck()
    assert deck.slide_width == SLIDE_WIDTH
    assert deck.slide_height == SLIDE_HEIGHT


def test_bullet_slide_caps_at_two_and_overflows_to_notes():
    deck = new_deck()
    add_bullet_slide(
        deck, "Heading", ["first point", "second point", "third point", "fourth point"]
    )
    slide = deck.slides[0]
    body = slide.placeholders[1].text_frame
    shown = [p.text for p in body.paragraphs if p.text.strip()]
    assert len(shown) == MAX_BULLETS == 2

    notes = slide.notes_slide.notes_text_frame.text
    assert "Third point." in notes and "Fourth point." in notes


def _content_bullet_counts(deck):
    """Bullet count for every Title-and-Content slide (body placeholder idx 1).
    List/example/title slides have no such placeholder and are exempt."""
    counts = []
    for slide in deck.slides:
        for placeholder in slide.placeholders:
            if placeholder.placeholder_format.idx == 1 and placeholder.has_text_frame:
                counts.append(
                    len([p for p in placeholder.text_frame.paragraphs if p.text.strip()])
                )
    return counts


def _sample_results():
    return [
        ObjectiveResult(
            objective="define variables",
            points=[f"Point {i} is a complete, self-contained sentence." for i in range(5)],
            examples=[
                {"kind": "prose", "text": "For example, x = 5.", "title": "V", "url": "u", "source": "Wikipedia"}
            ],
            citations=[{"title": "V", "url": "u", "source": "Wikipedia"}],
            confidence="high",
        ),
        ObjectiveResult(
            objective="write loops",
            points=["A loop repeats a block of code."],
            examples=[],
            citations=[],
            confidence="medium",
        ),
    ]


def test_module_deck_content_slides_obey_two_bullet_cap():
    deck = Presentation(io.BytesIO(build_module_deck("Intro to Python", _sample_results())))
    assert deck.slide_width == SLIDE_WIDTH  # widescreen + themed
    counts = _content_bullet_counts(deck)
    assert counts  # there is at least one content slide
    assert all(count <= MAX_BULLETS for count in counts)


def test_module_deck_overflow_points_land_in_notes():
    deck = Presentation(io.BytesIO(build_module_deck("Intro to Python", _sample_results())))
    objective_slide = next(
        s for s in deck.slides if s.shapes.title and s.shapes.title.text.startswith("Objective 1")
    )
    notes = objective_slide.notes_slide.notes_text_frame.text
    # 5 points, only 2 shown -> the rest are preserved in the notes.
    assert "Point 4 is a complete" in notes
