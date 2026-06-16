from knowledge.query import analyze
from knowledge.ranking import rank
from knowledge.sources.base import Passage
from knowledge.synthesize import FALLBACK_ANSWER, synthesize


def make_passage(text, title, url="http://example.com", source="Wikipedia"):
    return Passage(text=text, title=title, url=url, source=source, trust=1.0)


def build(query_text, passages):
    query = analyze(query_text)
    return query, synthesize(query, rank(query, passages))


def test_synthesis_has_answer_citations_and_markers():
    _, result = build(
        "What is cognitive dissonance?",
        [
            make_passage(
                "Cognitive dissonance is the mental discomfort felt when holding "
                "contradictory beliefs simultaneously in the mind. "
                "People experiencing cognitive dissonance often change a belief to reduce discomfort.",
                title="Cognitive dissonance",
            ),
            make_passage(
                "Leon Festinger introduced cognitive dissonance theory in 1957 after "
                "studying a doomsday cult whose prophecy failed to occur.",
                title="Leon Festinger",
                url="http://example.com/festinger",
            ),
        ],
    )
    assert "mental discomfort" in result["answer"]
    assert "[1]" in result["answer"]
    assert result["confidence"] in {"high", "medium", "low"}
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["title"]
    assert result["citations"][0]["url"]


def test_relevance_gate_drops_off_topic_titles():
    # The body mentions the keyword but the article is a different subject — an
    # honest gap is better than confidently citing the wrong article.
    _, result = build(
        "Use the accumulator pattern to process data",
        [
            make_passage(
                "The Hough transform obtains object candidates as local maxima in a "
                "so-called accumulator space constructed by the algorithm.",
                title="Hough transform",
            )
        ],
    )
    assert result["confidence"] == "none"
    assert result["citations"] == []


def test_relevance_gate_keeps_on_topic_title():
    _, result = build(
        "Explain photosynthesis",
        [
            make_passage(
                "Photosynthesis is the process plants use to make food from sunlight, "
                "water, and carbon dioxide.",
                title="Photosynthesis",
            )
        ],
    )
    assert result["confidence"] != "none"
    assert result["citations"]


def test_near_duplicates_are_removed():
    _, result = build(
        "What is photosynthesis?",
        [
            make_passage(
                "Photosynthesis is the process plants use to convert sunlight into "
                "chemical energy stored in glucose molecules.",
                title="Photosynthesis",
            ),
            make_passage(
                "Photosynthesis is the process that plants use to convert sunlight "
                "into chemical energy stored in glucose molecules.",
                title="Photosynthesis in plants",
                url="http://example.com/b",
            ),
        ],
    )
    # The two sentences are near-identical; only one should survive.
    assert result["answer"].count("convert sunlight") == 1
    assert len(result["citations"]) == 1


def test_irrelevant_content_yields_fallback():
    _, result = build(
        "What is quantum chromodynamics?",
        [
            make_passage(
                "The annual flower festival attracts thousands of visitors to the "
                "valley every spring season without fail.",
                title="Flowers",
            )
        ],
    )
    assert result["answer"] == FALLBACK_ANSWER or result["confidence"] in {"low", "none"}


def test_no_passages_yields_fallback():
    query = analyze("anything")
    result = synthesize(query, [])
    assert result["answer"] == FALLBACK_ANSWER
    assert result["confidence"] == "none"
    assert result["citations"] == []
