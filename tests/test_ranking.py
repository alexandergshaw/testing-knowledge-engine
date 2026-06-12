from knowledge.query import analyze
from knowledge.ranking import rank, split_sentences
from knowledge.sources.base import Passage, strip_html
from knowledge.sources.wikipedia import harvest_list


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


def test_media_work_demoted_for_non_media_question():
    query = analyze("What caused the fall of the Roman Empire?")
    film = make_passage(
        "The Fall of the Roman Empire is a 1964 American epic historical drama "
        "film directed by Anthony Mann about the fall of the Roman Empire.",
        title="The Fall of the Roman Empire",
    )
    history = make_passage(
        "The fall of the Roman Empire was the loss of central political "
        "control in the Western Roman Empire during late antiquity.",
        title="Fall of the Western Roman Empire",
    )
    ranked = rank(query, [film, history])
    assert ranked[0].passage.title == "Fall of the Western Roman Empire"


def test_strip_html_breaks_at_block_boundaries():
    text = strip_html(
        "<h2>Decorator Basics</h2><p>Functions are objects in Python.</p>"
        "<p>They can be passed around freely.</p>"
    )
    assert "Decorator Basics. Functions are objects in Python." in text
    assert ".." not in text


def test_strip_html_ends_sentence_at_removed_code_block():
    text = strip_html(
        "<p>You can accumulate decorators:</p><pre>@bread\n@ham\ndef x(): ...</pre>"
        "<p>The order you set the decorators matters.</p>"
    )
    assert "You can accumulate decorators." in text
    assert "@bread" not in text
    assert "decorators: The order" not in text


def test_rank_empty_passages():
    query = analyze("anything at all")
    assert rank(query, []) == []


def test_harvest_list_collapses_lesson_list():
    extract = (
        "This course comprises 12 lessons on Python programming.\n"
        "== Lessons ==\n"
        "Introduction\nVariables and Expressions\nConditions\nLoops\n"
        "Functions\nLists\nDictionaries\nClasses\n"
        "== See also ==\nSome closing prose that ends with a period."
    )
    sentence = harvest_list(extract, "Python Programming")
    assert sentence.startswith("Python Programming covers topics including:")
    assert "Variables and Expressions" in sentence
    assert "Classes" in sentence
    assert sentence.endswith(".")


def test_harvest_list_ignores_non_topic_sections():
    extract = (
        "Apex High School is a public high school in North Carolina.\n"
        "== Notable alumni ==\n"
        "Seth Frankoff, MLB pitcher\nJustin Jedlica\nMatt Mangini, MLB player\n"
        "Sio Moore, NFL linebacker\nLandon Powell, college baseball coach\n"
    )
    assert harvest_list(extract, "Apex High School") is None


def test_harvest_list_allows_outline_pages_anywhere():
    extract = (
        "== What type of language is Python? ==\n"
        "Programming language\nObject-oriented programming\n"
        "Functional programming\nScripting language\n"
    )
    sentence = harvest_list(extract, "Outline of the Python programming language")
    assert "Object-oriented programming" in sentence


def test_harvest_list_ignores_prose():
    extract = (
        "Cognitive dissonance is the mental discomfort felt when holding two "
        "contradictory beliefs.\nIt was proposed by Leon Festinger in 1957."
    )
    assert harvest_list(extract, "Cognitive dissonance") is None
