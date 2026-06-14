from knowledge import pipeline
from knowledge.query import analyze
from knowledge.sources.wikipedia import SimpleWikipediaSource


def test_simple_wikipedia_is_configured_for_layman_prose():
    src = SimpleWikipediaSource()
    assert src.host == "simple.wikipedia.org"
    assert src.name == "Simple English Wikipedia"
    assert src.trust == 1.0
    # Prose only: intros (the cleanest layman summary), no list/curriculum
    # harvesting (that's Wikiversity/Wikibooks territory).
    assert src.intro_only is True
    assert src.harvest_lists is False


def test_simple_wikipedia_parses_mediawiki_extract(monkeypatch):
    payload = {
        "query": {
            "pages": {
                "42": {
                    "index": 1,
                    "title": "Photosynthesis",
                    "extract": (
                        "Photosynthesis is the way that plants make food. "
                        "Plants use sunlight, water, and carbon dioxide to make sugar."
                    ),
                }
            }
        }
    }
    src = SimpleWikipediaSource()
    monkeypatch.setattr(src, "get", lambda url, params: payload)

    passages = src.search(analyze("What is photosynthesis?"))

    assert len(passages) == 1
    passage = passages[0]
    assert passage.title == "Photosynthesis"
    assert passage.source == "Simple English Wikipedia"
    assert passage.url == "https://simple.wikipedia.org/wiki/Photosynthesis"
    assert passage.text.startswith("Photosynthesis is the way that plants make food.")


def test_simple_wikipedia_requests_intro_only(monkeypatch):
    captured = {}

    def fake_get(url, params):
        captured["params"] = params
        return {"query": {"pages": {}}}

    src = SimpleWikipediaSource()
    monkeypatch.setattr(src, "get", fake_get)
    src.search(analyze("What is gravity?"))

    assert captured["params"]["exintro"] == 1


def test_select_sources_includes_simple_wikipedia():
    # The layman generalist must run on an ordinary definition query.
    sources = pipeline.select_sources(analyze("What is gravity?"))
    assert pipeline._simple_wikipedia in sources
    # Still alongside the regular encyclopedia, not replacing it.
    assert pipeline._wikipedia in sources
