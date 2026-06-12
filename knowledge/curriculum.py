"""Curriculum specialist path: for "what topics does a <subject> course
cover" questions, skip fragile keyword search entirely. Fetch known
curriculum pages by title (Wikiversity courses, Wikibooks textbook TOCs,
Wikipedia outlines), harvest their topic lists, and merge them into one
consensus-ordered list — corroboration across independent sources is the
ranking signal."""

import logging
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from .query import RELATED_CURRICULUM, STOPWORDS, content_tokens, tokenize
from .ranking import rank
from .sources.base import Passage
from .sources.wikipedia import (
    WikibooksSource,
    WikipediaSource,
    WikiversitySource,
    harvest_items,
)
from .synthesize import jaccard

log = logging.getLogger(__name__)

MIN_TOPICS = 4
MAX_TOPICS = 18
MERGE_JACCARD = 0.5
MAX_ITEM_WORDS = 6

_wikipedia = WikipediaSource()
_wikiversity = WikiversitySource()
_wikibooks = WikibooksSource()

# Items that are link-farm leftovers, not course topics.
_NOISE = re.compile(
    r"^\w+:|https?://|www\.|\.(com|org|net|edu|io)\b|^see also$|^references?$"
    r"|^external links?$|^further reading$"
    r"|^(list|lists|comparison|index|glossary|timeline|outline) of\b",
    re.IGNORECASE,
)


def candidate_titles(query):
    """Deterministic page titles per source. MediaWiki redirects resolve the
    rest ('Outline of JavaScript' -> 'Outline of the JavaScript programming
    language')."""
    subject = query.subject
    if query.is_programming:
        # Language subjects get "X Programming" course titles; subjects that
        # already say "programming" ("Object-oriented programming") don't.
        if "programming" in subject.lower():
            course_title = subject
            outline_titles = [f"Outline of {subject.lower()}", f"Outline of {subject}"]
        else:
            course_title = f"{subject} Programming"
            outline_titles = [
                f"Outline of the {subject} programming language",
                f"Outline of {subject}",
            ]
        plan = {
            _wikiversity: [course_title, "Applied Programming"],
            _wikibooks: [course_title, subject],
            _wikipedia: outline_titles,
        }
    else:
        plan = {
            _wikiversity: [subject, f"Introduction to {subject}", f"{subject} course"],
            _wikibooks: [subject],
            _wikipedia: [f"Outline of {subject.lower()}", f"Outline of {subject}"],
        }
    # A subject without its own curriculum pages can borrow its parent
    # field's ("ethical hacking" -> Computer security).
    related = RELATED_CURRICULUM.get(subject.lower())
    if related:
        plan[_wikiversity] = plan.get(_wikiversity, []) + [related]
        plan[_wikipedia] = plan.get(_wikipedia, []) + [f"Outline of {related.lower()}"]

    # MediaWiki titles are case-sensitive after the first letter; course pages
    # are often Title Case ("Computer Security"). Existence checks are batched,
    # so extra variants are cheap.
    for titles in plan.values():
        titles.extend(t.title() for t in list(titles) if t.title() not in titles)
    return plan


def _fetch_all(query):
    """(source, title, raw_extract, url) for every existing candidate page."""
    plan = candidate_titles(query)
    pages = []
    with ThreadPoolExecutor(max_workers=len(plan)) as executor:
        futures = {
            executor.submit(source.fetch_titles, titles): source
            for source, titles in plan.items()
        }
        for future, source in futures.items():
            try:
                for title, raw, url in future.result(timeout=25):
                    pages.append((source, title, raw, url))
            except Exception:
                log.warning("curriculum fetch failed for %s", source.name, exc_info=True)
    return pages


def _content_relevant(raw, subject):
    """Search ranking lies ('Outline of Ubuntu' for 'ethical hacking');
    the subject's own words appearing repeatedly in the page doesn't."""
    lowered = raw.lower()
    tokens = [t for t in tokenize(subject) if t not in STOPWORDS]
    return any(lowered.count(token) >= 3 for token in tokens)


def _find_outline_titles(subject):
    """Candidate 'Outline of X' pages: try the full subject, then its head
    noun ('ethical hacking' -> 'hacking')."""
    words = subject.split()
    attempts = [subject] + ([words[-1]] if len(words) > 1 else [])
    for terms in attempts:
        hits = _wikipedia.search_titles(f'intitle:"outline of" {terms}', 3)
        outlines = [t for t in hits if t.lower().startswith("outline of")]
        if outlines:
            return outlines[:2]
    return []


def search_fallback_pages(query):
    """When no candidate title exists (unlexiconed subjects like 'Ethical
    hacking'), find curriculum material by search: a content-validated
    Wikipedia outline, the subject's own article (its section headings are a
    topical breakdown), and the top Wikiversity course pages."""
    pages = []
    try:
        for title, raw, url in _wikipedia.fetch_titles(
            _find_outline_titles(query.subject)
        ):
            if _content_relevant(raw, query.subject):
                pages.append((_wikipedia, title, raw, url))
                break
    except Exception:
        log.warning("outline search fallback failed", exc_info=True)
    try:
        pages.extend(
            (_wikipedia, title, raw, url)
            for title, raw, url in _wikipedia.fetch_titles([query.subject])
        )
    except Exception:
        log.warning("subject article fallback failed", exc_info=True)
    try:
        course_titles = _wikiversity.search_titles(query.subject, 2)
        pages.extend(
            (_wikiversity, title, raw, url)
            for title, raw, url in _wikiversity.fetch_titles(course_titles)
        )
    except Exception:
        log.warning("wikiversity search fallback failed", exc_info=True)
    return pages


def _clean_item(item):
    item = re.sub(r"\(.*?\)", "", item)          # drop parentheticals
    item = re.sub(r"\s*[—–-]\s.*$", "", item)    # drop trailing " — gloss"
    item = re.sub(r"\s+", " ", item).strip(" ,;:—–-")
    return item


def _usable(item):
    return (
        item
        and len(item.split()) <= MAX_ITEM_WORDS
        and not _NOISE.search(item)
        and any(c.isalpha() for c in item)
    )


def aggregate(per_page_items, neutral_positions=frozenset()):
    """per_page_items: list of (citation_index, [items in page order]).
    Merge near-duplicate topics across pages; rank by corroboration count,
    then by average normalized position (consensus pedagogical order).
    Pages in neutral_positions (e.g. alphabetical lists) contribute a flat
    0.5 position — their order carries no pedagogy."""
    topics = []  # {names: Counter, tokens, citations: set, positions: []}
    for citation_index, items in per_page_items:
        cleaned = [i for i in (_clean_item(item) for item in items) if _usable(i)]
        total = len(cleaned)
        seen_here = set()
        for position, item in enumerate(cleaned):
            tokens = content_tokens(item)
            if not tokens:
                continue
            match = None
            for topic in topics:
                if jaccard(tokens, topic["tokens"]) >= MERGE_JACCARD:
                    match = topic
                    break
            if match is None:
                match = {
                    "names": Counter(),
                    "tokens": tokens,
                    "citations": set(),
                    "positions": [],
                }
                topics.append(match)
            if id(match) in seen_here:
                continue  # same page listing a topic twice isn't corroboration
            seen_here.add(id(match))
            match["names"][item] += 1
            match["citations"].add(citation_index)
            match["positions"].append(
                0.5
                if citation_index in neutral_positions
                else position / max(total - 1, 1)
            )

    def sort_key(topic):
        avg_position = sum(topic["positions"]) / len(topic["positions"])
        return (-len(topic["citations"]), avg_position)

    ordered = sorted(topics, key=sort_key)[:MAX_TOPICS]
    return [
        {
            "name": topic["names"].most_common(1)[0][0],
            "citations": sorted(topic["citations"]),
            # consensus pedagogical position (0 = start of course, 1 = end)
            "position": sum(topic["positions"]) / len(topic["positions"]),
        }
        for topic in ordered
    ]


def _intro_sentence(query, pages):
    """Best prose sentence from the fetched pages, by the normal BM25 rank."""
    passages = [
        Passage(
            text=source.clean(raw)[:2000],
            title=title,
            url=url,
            source=source.name,
            trust=source.trust,
        )
        for source, title, raw, url in pages
    ]
    ranked = rank(query, passages)
    if ranked and ranked[0].score > 0:
        return ranked[0].text
    return ""


def answer_curriculum(query):
    """Structured curriculum answer, or None to fall through to the general
    pipeline."""
    pages = _fetch_all(query)
    if not pages:
        return None

    citations, per_page_items = [], []
    for source, title, raw, url in pages:
        items = harvest_items(raw, title)
        if not items:
            continue
        citations.append({"title": title, "url": url, "source": source.name})
        per_page_items.append((len(citations), items))

    topics = aggregate(per_page_items)
    if len(topics) < MIN_TOPICS:
        return None

    corroborating = {c for topic in topics for c in topic["citations"]}
    confidence = "high" if len(corroborating) >= 2 else "medium"

    intro = (
        f"A {query.subject} course typically covers the following topics, "
        f"drawn from {len(citations)} published curricula."
    )
    prose = _intro_sentence(query, pages)
    answer_text = f"{prose} {intro}".strip() if prose else intro

    return {
        "answer": answer_text,
        "topics": topics,
        "citations": citations,
        "confidence": confidence,
    }
