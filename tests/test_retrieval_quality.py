"""Offline retrieval-quality benchmark (replays recorded source responses).

Bar: retrieval must be *relevant or an honest gap*. A case passes when the engine
either cites a topically-relevant article (a title containing one of the case's
keywords) or returns nothing (confidence "none"). It FAILS when it is
confidently wrong — citing an off-topic article with non-none confidence
(e.g. "accumulator pattern" -> "Hough transform").

`xfail` cases are baseline gaps the D-b relevance gate is expected to fix.
Re-record fixtures with: python -m scripts.record_retrieval_fixtures
"""

import pytest

import knowledge.pipeline as pipeline
from knowledge.query import analyze
from tests.retrieval_cassette import install_replay, load
from tests.retrieval_eval_cases import CASES


@pytest.fixture(scope="module")
def cassette():
    return load()


def _acceptable(case, result):
    citations = result.get("citations") or []
    if result.get("confidence") == "none" or not citations:
        return True  # an honest gap is acceptable
    titles = " ".join(c.get("title", "").lower() for c in citations)
    return any(keyword in titles for keyword in case["keywords"])


def _param(case):
    marks = [pytest.mark.xfail(reason="retrieval gap — fixed in D-b", strict=False)] if case.get("xfail") else []
    return pytest.param(case, id=case["objective"][:45], marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in CASES])
def test_retrieval_is_relevant_or_honest_gap(case, cassette, monkeypatch):
    install_replay(cassette, monkeypatch)
    result = pipeline._attempt(analyze(case["objective"]))
    assert _acceptable(case, result), (
        f"{case['objective']!r} cited "
        f"{[c['title'] for c in result.get('citations', [])]} at "
        f"confidence={result.get('confidence')} — expected a {case['keywords']} match or a gap"
    )
