"""Shared retrieval logic for the benchmark — used by both the recorder
(scripts/record_retrieval_fixtures.py) and the test (test_retrieval_quality.py)
so they exercise the exact same path.

Mirrors the lecture retrieval branch: analyze -> domain anchoring -> profile
routing -> fetch -> rank -> synthesize.
"""

import knowledge.pipeline as pipeline
from knowledge.aliases import aliases_for
from knowledge.query import analyze
from knowledge.synthesize import CONTENT_RELEVANCE_SOURCES


def run_case(case):
    """Return the synthesize result ({answer, citations, confidence}) for an eval
    case, retrieving with its domain routing and alias variants (the same path
    the lecture flow uses)."""
    query = analyze(case["objective"])
    domain = case.get("domain")
    if domain == "programming" and "programming" not in query.search_terms:
        query.search_terms = f"{query.search_terms} programming".strip()
    result, _, _ = pipeline.retrieve(query, domain, aliases_for(case["objective"]))
    return result


def acceptable(case, result):
    """Pass bar.

    - Normal cases: relevant OR an honest gap (never confidently wrong).
    - `require_relevant` cases (the gap corpus): must cite a topically-relevant
      source — a gap is NOT good enough; these are what we're trying to close.
    """
    citations = result.get("citations") or []
    is_gap = result.get("confidence") == "none" or not citations
    titles = " ".join(c.get("title", "").lower() for c in citations)
    # Relevant = a title keyword match, or any cite from a Q&A/task source (which
    # only passes synthesize's gate via on-topic content, not its title).
    relevant = any(keyword in titles for keyword in case["keywords"]) or any(
        c.get("source") in CONTENT_RELEVANCE_SOURCES for c in citations
    )
    if case.get("require_relevant"):
        return relevant
    return is_gap or relevant
