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
from .sources.wikipedia import WikipediaSource, WikiversitySource, WiktionarySource
from .synthesize import FALLBACK_ANSWER, synthesize

log = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 10

_cache = TTLCache(ttl_seconds=3600)

_wikipedia = WikipediaSource()
_wikiversity = WikiversitySource()
_wiktionary = WiktionarySource()
_stackoverflow = StackExchangeSource("stackoverflow", "Stack Overflow", 0.9)
_cseducators = StackExchangeSource("cseducators", "CS Educators Stack Exchange", 0.85)
_duckduckgo = DuckDuckGoSource()


def select_sources(query):
    """Rule-based domain routing. Generalists always run; specialists are
    added when the question looks like their domain. Misrouting is cheap —
    BM25 ranking buries irrelevant results."""
    sources = [_wikipedia, _duckduckgo]
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


def _attempt(query):
    passages = fetch(query, select_sources(query))
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
