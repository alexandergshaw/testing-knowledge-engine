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


def test_select_sources_domain_routing():
    query = analyze("Use the accumulator pattern to process data")
    assert not query.is_programming
    # Default routing (no domain) doesn't reach Stack Overflow for this wording.
    base = pipeline.select_sources(query)
    assert pipeline._stackoverflow not in base
    # A programming deck routes every objective to the code experts.
    routed = pipeline.select_sources(query, domain="programming")
    assert pipeline._stackoverflow in routed and pipeline._cseducators in routed
    # A quantitative deck reaches the lesson/worked-example sources.
    quant = pipeline.select_sources(analyze("Solve the equation for x"), domain="quantitative")
    assert pipeline._wikiversity in quant and pipeline._wikibooks in quant


def test_aliases_for_concepts():
    from knowledge.aliases import aliases_for

    assert "accumulator factory" in aliases_for("Use the accumulator pattern to process data")
    assert aliases_for("Explain photosynthesis") == []


def test_programming_routing_includes_rosetta_and_wikibooks():
    routed = pipeline.select_sources(analyze("Write a function"), domain="programming")
    assert pipeline._rosettacode in routed
    assert pipeline._wikibooks in routed
    # Rosetta is configured against its MediaWiki API and judged by content.
    assert pipeline._rosettacode.host == "rosettacode.org"
    assert pipeline._rosettacode.name == "Rosetta Code"


def test_select_sources_default_domain_unchanged():
    # domain=None must be identical to before (so the retrieval benchmark holds).
    query = analyze("Use the accumulator pattern to process data")
    assert pipeline.select_sources(query) == [
        pipeline._wikipedia, pipeline._simple_wikipedia, pipeline._duckduckgo
    ]
