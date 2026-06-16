"""Offline retrieval-quality benchmark (replays recorded source responses).

Two bars:
- Correctness cases (CASES): relevant OR an honest gap — never confidently wrong
  (e.g. "accumulator pattern" must not cite "Hough transform").
- Gap corpus (GAP_CORPUS, require_relevant): must cite topically-relevant
  content — these are programming idioms/tasks we're trying to *close*. They
  start xfail; the research loop (R-a/R-b/R-c) flips them as coverage improves.

Re-record fixtures with: python -m scripts.record_retrieval_fixtures
"""

import pytest

from tests.retrieval_cassette import install_replay, load
from tests.retrieval_eval import acceptable, run_case
from tests.retrieval_eval_cases import ALL_CASES


@pytest.fixture(scope="module")
def cassette():
    return load()


def _param(case):
    marks = [pytest.mark.xfail(reason="open retrieval gap", strict=False)] if case.get("xfail") else []
    return pytest.param(case, id=case["objective"][:45], marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in ALL_CASES])
def test_retrieval_quality(case, cassette, monkeypatch):
    install_replay(cassette, monkeypatch)
    result = run_case(case)
    assert acceptable(case, result), (
        f"{case['objective']!r} cited "
        f"{[c['title'] for c in result.get('citations', [])]} at "
        f"confidence={result.get('confidence')} — "
        f"{'needs a relevant source' if case.get('require_relevant') else 'expected a match or a gap'}"
    )
