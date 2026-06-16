"""Orchestrator: analyze -> route -> parallel fetch -> rank -> synthesize."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError

from . import curriculum
from .cache import TTLCache
from .query import analyze
from .ranking import rank
from .sources.duckduckgo import DuckDuckGoSource
from .sources.stackexchange import StackExchangeSource
from .sources.wikipedia import (
    SimpleWikipediaSource,
    WikibooksSource,
    WikipediaSource,
    WikiversitySource,
    WiktionarySource,
)
from .synthesize import FALLBACK_ANSWER, synthesize

log = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 10

_cache = TTLCache(ttl_seconds=3600)

_wikipedia = WikipediaSource()
_simple_wikipedia = SimpleWikipediaSource()
_wikiversity = WikiversitySource()
_wikibooks = WikibooksSource()
_wiktionary = WiktionarySource()
_stackoverflow = StackExchangeSource("stackoverflow", "Stack Overflow", 0.9)
_cseducators = StackExchangeSource("cseducators", "CS Educators Stack Exchange", 0.85)
_duckduckgo = DuckDuckGoSource()


def select_sources(query, domain=None):
    """Rule-based domain routing. Generalists always run; specialists are
    added when the question looks like their domain. Misrouting is cheap —
    BM25 ranking and the relevance gate bury irrelevant results.

    `domain` is the deck-level profile ("programming"/"quantitative"): it
    broadens the source set to that domain's experts even when an individual
    objective's wording didn't trip the per-query flags (e.g. "accumulator
    pattern" reads as neither programming nor education, but in a programming
    deck it should still reach Stack Overflow)."""
    # Simple English Wikipedia rides with the generalists: when it has an
    # article its plain-language prose competes sentence-for-sentence with the
    # regular encyclopedia, which is what the layman lecture fallback wants.
    sources = [_wikipedia, _simple_wikipedia, _duckduckgo]
    if query.is_education:
        # Curriculum/teaching questions: Stack Overflow's code Q&A is noise
        # here — the educators' site and Wikiversity courses are the experts.
        sources.append(_wikiversity)
        if query.is_programming:
            sources.append(_cseducators)
    elif query.is_programming:
        sources.append(_stackoverflow)
    if query.qtype == "definition" and len(query.keywords) <= 2:
        sources.append(_wiktionary)

    # Deck-profile routing (lecture flow only; default domain=None is unchanged).
    if domain == "programming":
        for source in (_stackoverflow, _cseducators):
            if source not in sources:
                sources.append(source)
    elif domain == "quantitative":
        for source in (_wikiversity, _wikibooks):
            if source not in sources:
                sources.append(source)
    return sources


def fetch(query, sources):
    passages = []
    with ThreadPoolExecutor(max_workers=len(sources)) as executor:
        futures = {executor.submit(s.search, query): s for s in sources}
        try:
            for future in as_completed(futures, timeout=FETCH_TIMEOUT_SECONDS):
                source = futures[future]
                try:
                    passages.extend(future.result())
                except Exception:
                    log.warning("source %s failed", source.name, exc_info=True)
        except FuturesTimeoutError:
            log.warning("fetch timed out; continuing with partial results")
    return passages


def _attempt(query, domain=None):
    passages = fetch(query, select_sources(query, domain))
    if not passages:
        return {"answer": FALLBACK_ANSWER, "citations": [], "confidence": "none"}
    return synthesize(query, rank(query, passages))


def answer(question):
    key = " ".join(question.lower().split())
    cached = _cache.get(key)
    if cached is not None:
        return cached

    query = analyze(question)

    # Curriculum questions get the specialist path: deterministic lookups of
    # course/outline pages and cross-source topic aggregation.
    if query.is_curriculum and query.subject:
        try:
            result = curriculum.answer_curriculum(query)
        except Exception:
            log.warning("curriculum path failed", exc_info=True)
            result = None
        if result is not None:
            result["question"] = query.raw
            _cache.set(key, result)
            return result

    # If a search-term variant finds nothing, relax: full keyword bag, then
    # the bare topic phrase. Stops at the first variant that yields an answer.
    variants = [query.search_terms, " ".join(query.keywords), query.topic]
    result = {"answer": FALLBACK_ANSWER, "citations": [], "confidence": "none"}
    tried = set()
    for terms in variants:
        if not terms or terms in tried:
            continue
        tried.add(terms)
        query.search_terms = terms
        result = _attempt(query)
        if result["confidence"] != "none":
            break

    result["question"] = query.raw
    _cache.set(key, result)
    return result
