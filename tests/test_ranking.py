from knowledge.query import analyze
from knowledge.ranking import rank, split_sentences
from knowledge.sources.base import Passage


def make_passage(text, trust=1.0, source="Wikipedia", title="Test", url="http://x"):
    return Passage(text=text, title=title, url=url, source=source, trust=trust)


def test_relevant_sentence_ranks_first():
    query = analyze("What is cognitive dissonance?")
    passage = make_passage(
        "Cognitive dissonance is the mental discomfort felt when holding two "
        "contradictory beliefs at the same time. "
        "The weather in Spain is generally warm during the summer months. "
        "Festinger proposed the theory of cognitive dissonance in 1957 after a field study."
    )
    ranked = rank(query, [passage])
    assert ranked
    assert "mental discomfort" in ranked[0].text
    assert ranked[0].score > ranked[-1].score
    assert "weather in Spain" in ranked[-1].text


def test_trust_weight_breaks_ties():
    query = analyze("What is photosynthesis?")
    text = (
        "Photosynthesis is the process plants use to convert light into energy. "
        "It happens primarily within the chloroplasts of plant cells everywhere."
    )
    trusted = make_passage(text, trust=1.0, title="A")
    untrusted = make_passage(text, trust=0.5, title="B")
    ranked = rank(query, [untrusted, trusted])
    assert ranked[0].passage.title == "A"


def test_split_sentences_filters_fragments():
    sentences = split_sentences(
        "Too short. This sentence is comfortably long enough to keep around for "
        "synthesis purposes. Tiny."
    )
    assert len(sentences) == 1
    assert sentences[0].startswith("This sentence")


def test_title_match_outranks_tangent_article():
    query = analyze("What is cognitive dissonance?")
    text = (
        "Cognitive dissonance is the mental discomfort felt when holding two "
        "contradictory beliefs at the same time in the mind."
    )
    main = make_passage(text, title="Cognitive dissonance")
    tangent = make_passage(text, title="Vicarious cognitive dissonance")
    ranked = rank(query, [tangent, main])
    assert ranked[0].passage.title == "Cognitive dissonance"


def test_rank_empty_passages():
    query = analyze("anything at all")
    assert rank(query, []) == []
