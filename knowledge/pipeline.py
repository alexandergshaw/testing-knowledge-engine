"""Orchestrator: analyze -> route -> parallel fetch -> rank -> synthesize."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeoutError

from .cache import TTLCache
from .query import analyze
from .ranking import rank
from .sources.duckduckgo import DuckDuckGoSource
from .sources.stackexchange import StackOverflowSource
from .sources.wikipedia import WikipediaSource, WiktionarySource
from .synthesize import FALLBACK_ANSWER, synthesize

log = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 10

_cache = TTLCache(ttl_seconds=3600)

_wikipedia = WikipediaSource()
_wiktionary = WiktionarySource()
_stackoverflow = StackOverflowSource()
_duckduckgo = DuckDuckGoSource()


def select_sources(query):
    """Rule-based domain routing. Generalists always run; specialists are
    added when the question looks like their domain. Misrouting is cheap —
    BM25 ranking buries irrelevant results."""
    sources = [_wikipedia, _duckduckgo]
    if query.is_programming:
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


def answer(question):
    key = " ".join(question.lower().split())
    cached = _cache.get(key)
    if cached is not None:
        return cached

    query = analyze(question)
    passages = fetch(query, select_sources(query))
    if not passages:
        return {"answer": FALLBACK_ANSWER, "citations": [], "confidence": "none"}

    result = synthesize(query, rank(query, passages))
    result["question"] = query.raw
    _cache.set(key, result)
    return result
