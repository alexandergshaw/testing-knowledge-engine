"""Course-description -> weekly topic schedule.

Parses a free-text college course description (rule-based, no LLM), pulls a
consensus-ordered topic list from published curricula (Wikiversity courses,
Wikibooks textbooks, Wikipedia outlines via knowledge.curriculum), guarantees
topics the description explicitly requires, and allocates everything across
the requested number of term weeks."""

import re

from .cache import TTLCache
from .curriculum import MIN_TOPICS, _fetch_all, aggregate, search_fallback_pages
from .query import (
    EDUCATION_TERMS,
    FIELD_SUBJECTS,
    LEVEL_TERMS,
    STOPWORDS,
    SUBJECT_ALIASES,
    SUBJECT_PHRASES,
    QUESTION_WORDS,
    AnalyzedQuery,
    content_tokens,
    tokenize,
    _CODE_PATTERN,
    _PROGRAMMING_TERMS,
)
from .sources.wikipedia import harvest_headings, harvest_items
from .synthesize import jaccard

MIN_WEEKS = 1
MAX_WEEKS = 52
MAX_MENTION_WORDS = 6
MENTION_MATCH_JACCARD = 0.34

_cache = TTLCache(ttl_seconds=3600)

# "covering X, Y, and Z" -style requirement phrases in course descriptions.
_MENTION_LEADS = re.compile(
    r"\b(?:covering|covers|includ(?:es|ing|e)|"
    r"introduc(?:es|ing|e)(?:\s+students?\s+to)?|introduction to|"
    r"topics such as|such as|emphasis on|emphasizes|"
    r"focusing on|focuses on|focus on|students will learn(?: about)?|"
    r"learn about|explores|exploring|examines|examining)\s+([^.;:!?]{3,250})",
    re.IGNORECASE,
)
_MENTION_SPLIT = re.compile(r",|;|\band\b|\bas well as\b|\bplus\b", re.IGNORECASE)
# Leading qualifiers that aren't part of the topic name.
_MENTION_TRIM = re.compile(
    r"^(?:the|a|an|basic|basics of|fundamental|fundamentals of|core|key|"
    r"essential|advanced|introductory|various|common|general)\s+",
    re.IGNORECASE,
)


# Single-token aliases too ambiguous to trust bare in prose ("go over",
# "R rating"): only count them next to a language cue.
_AMBIGUOUS_ALIASES = {"go", "r"}

_WORD = r"[A-Za-z][\w+#&/-]*"
_STOP_AHEAD = (
    r"(?=\s*[,.;:!?]|\s+(?:designed|intended|covering|exploring|examining|"
    r"that|which|for|where|with)\b|\s*$)"
)
# Descriptions state their subject syntactically — these beat any lexicon.
_SUBJECT_STATEMENTS = [
    # "Ethical Hacking is a course designed to ..."
    re.compile(
        rf"^\W*({_WORD}(?:\s+{_WORD}){{0,4}}?)\s+is\s+(?:a|an|this)\s+(?:\w+\s+){{0,3}}?course\b",
        re.IGNORECASE,
    ),
    # "a course in Python programming" / "course on world history"
    re.compile(
        rf"\bcourse\s+(?:in|on|about)\s+(?:the\s+)?({_WORD}(?:\s+{_WORD}){{0,4}}?){_STOP_AHEAD}",
        re.IGNORECASE,
    ),
    # "Introduction to Microeconomics"
    re.compile(
        rf"\bintroduction\s+to\s+({_WORD}(?:\s+{_WORD}){{0,4}}?){_STOP_AHEAD}",
        re.IGNORECASE,
    ),
    # "This course is Object Oriented Programming." — subject after "course
    # is". Function words are excluded so "course is for students..." or
    # "course is designed to..." don't capture.
    re.compile(
        rf"\bcourse\s+is\s+(?!for\b|to\b|about\b|designed\b|intended\b|meant\b|"
        rf"a\b|an\b|the\b|one\b|part\b)({_WORD}(?:\s+{_WORD}){{0,4}}?){_STOP_AHEAD}",
        re.IGNORECASE,
    ),
    # "A cybersecurity course." — subject as noun-phrase before "course".
    # Level/education filler ("an introductory college course") normalizes
    # away to nothing, so this pattern only wins when a real subject is named.
    re.compile(
        rf"\b(?:a|an|the)\s+({_WORD}(?:\s+{_WORD}){{0,3}}?)\s+course\b",
        re.IGNORECASE,
    ),
]


def _normalize_subject(phrase):
    """Canonicalize an extracted subject phrase: strip level/education filler,
    map known names to their canonical form, otherwise sentence-case as-is."""
    words = [
        w
        for w in phrase.split()
        if w.lower() not in LEVEL_TERMS
        and w.lower() not in EDUCATION_TERMS
        and w.lower() not in {"a", "an", "the"}
    ]
    if not words:
        return ""
    cleaned = " ".join(words)
    lowered = cleaned.lower()
    for known_phrase, canonical in SUBJECT_PHRASES.items():
        if known_phrase in lowered:
            return canonical
    for token in tokenize(cleaned):
        if token in SUBJECT_ALIASES and token not in _AMBIGUOUS_ALIASES:
            return SUBJECT_ALIASES[token]
    if len(words) == 1 and lowered in FIELD_SUBJECTS:
        return FIELD_SUBJECTS[lowered]
    return cleaned[0].upper() + cleaned[1:].lower()


def _resolve_subject(description):
    """The subject a course description names. A syntactic statement of the
    subject ('Ethical Hacking is a course...') beats lexicon matching — the
    lexicon can't know every subject, and partial hits ('ethics') mislead.
    Among lexicon hits, the earliest wins: descriptions lead with their
    subject ('a course in Python programming, covering data structures...')."""
    for pattern in _SUBJECT_STATEMENTS:
        match = pattern.search(description)
        if match:
            subject = _normalize_subject(match.group(1))
            if subject:
                return subject

    text = description.lower()
    candidates = []
    for phrase, canonical in SUBJECT_PHRASES.items():
        position = text.find(phrase)
        if position >= 0:
            candidates.append((position, -len(phrase), canonical))
    for lexicon in (SUBJECT_ALIASES, FIELD_SUBJECTS):
        for token, canonical in lexicon.items():
            if token in _AMBIGUOUS_ALIASES:
                match = re.search(
                    rf"\b{re.escape(token)}\s+(?:programming|language)\b", text
                )
            else:
                match = re.search(rf"(?<![\w+#]){re.escape(token)}(?![\w+#])", text)
            if match:
                candidates.append((match.start(), -len(token), canonical))
    return min(candidates)[2] if candidates else ""


def analyze_description(description):
    """An AnalyzedQuery for a course description, so the curriculum module's
    deterministic page lookups and ranking work unchanged."""
    keywords = []
    for token in tokenize(description):
        if token in STOPWORDS or token in QUESTION_WORDS:
            continue
        if token not in keywords:
            keywords.append(token)

    tokens = set(tokenize(description))
    is_programming = bool(tokens & _PROGRAMMING_TERMS) or bool(
        _CODE_PATTERN.search(description)
    )
    subject = _resolve_subject(description)
    return AnalyzedQuery(
        raw=description.strip(),
        topic=subject.lower(),
        keywords=keywords,
        qtype="list",
        is_programming=is_programming,
        is_education=True,
        is_curriculum=True,
        subject=subject,
        search_terms=subject,
    )


def extract_mentions(description):
    """Topic phrases the description explicitly requires, in order."""
    mentions = []
    for chunk in _MENTION_LEADS.findall(description):
        for piece in _MENTION_SPLIT.split(chunk):
            # A lead-word can nest inside another's chunk ("learn ...,
            # covering variables") — trim it off the piece too.
            piece = _MENTION_LEADS.sub(lambda m: m.group(1), piece.strip(" ."))
            phrase = _MENTION_TRIM.sub("", piece.strip(" .")).strip()
            if not phrase or len(phrase.split()) > MAX_MENTION_WORDS:
                continue
            if not any(c.isalpha() for c in phrase):
                continue
            if phrase.lower() not in (m.lower() for m in mentions):
                mentions.append(phrase)
    return mentions


# Wikiversity course pages are complete, ordered curricula — their items are
# trustworthy alone. Wikibooks TOCs harvest partially (mid-book deep cuts with
# misleading positions) and Wikipedia outlines are link farms, so items from
# those count only when corroborated or required by the description.
CURATED_SOURCES = {"Wikiversity"}


def _matches_mention(topic, mentions):
    topic_tokens = content_tokens(topic["name"])
    return any(
        jaccard(content_tokens(m), topic_tokens) >= MENTION_MATCH_JACCARD
        for m in mentions
    )


def _filter_topics(topics, citations, mentions):
    """Keep a topic if it's corroborated by 2+ pages, comes from a curated
    curriculum page, or satisfies a description requirement."""
    curated = {
        index
        for index, citation in enumerate(citations, start=1)
        if citation["source"] in CURATED_SOURCES
    }
    kept = [
        t
        for t in topics
        if len(t["citations"]) >= 2
        or set(t["citations"]) & curated
        or _matches_mention(t, mentions)
    ]
    # A sparse subject (one textbook, no course page) is better served by an
    # unfiltered list than by nothing.
    return kept if len(kept) >= MIN_TOPICS else topics


def _weave_mentions(topics, mentions):
    """Description-required topics are non-negotiable. Unmatched ones are
    inserted at a pseudo-position from their order in the description —
    descriptions list topics in teaching order too."""
    total = len(mentions) or 1
    for index, mention in enumerate(mentions):
        mention_tokens = content_tokens(mention)
        if not mention_tokens:
            continue
        if any(
            jaccard(mention_tokens, content_tokens(t["name"])) >= MENTION_MATCH_JACCARD
            for t in topics
        ):
            continue
        topics.append(
            {
                "name": mention[:1].upper() + mention[1:],
                "citations": [],
                "position": (index + 0.5) / total,
            }
        )
    topics.sort(key=lambda t: t.get("position", 1.0))
    return topics


ALPHA_MIN_ITEMS = 8
ALPHA_ORDER_FRACTION = 0.7
ALPHA_SAMPLE_TO = 24


def _is_alphabetical(items):
    """An alphabetically ordered list (outline branch indexes, glossaries) is
    a catalog, not a teaching order."""
    if len(items) < ALPHA_MIN_ITEMS:
        return False
    lowered = [i.casefold() for i in items]
    ordered = sum(a <= b for a, b in zip(lowered, lowered[1:]))
    return ordered / (len(items) - 1) >= ALPHA_ORDER_FRACTION


def _sample_evenly(items, limit):
    if len(items) <= limit:
        return items
    step = len(items) / limit
    return [items[int(i * step)] for i in range(limit)]


def allocate(topic_names, weeks):
    """Distribute ordered topics across term weeks. More topics than weeks:
    contiguous groups. Fewer: long topics span extra weeks, plus review weeks."""
    weeks = max(MIN_WEEKS, min(int(weeks), MAX_WEEKS))
    count = len(topic_names)
    if count == 0:
        return []

    if count >= weeks:
        base, remainder = divmod(count, weeks)
        groups, index = [], 0
        for week in range(weeks):
            size = base + (1 if week < remainder else 0)
            groups.append(list(topic_names[index : index + size]))
            index += size
    else:
        reserve_final = 1 if weeks > count else 0
        reserve_midterm = 1 if weeks >= 10 and (weeks - count) >= 2 else 0
        slots = weeks - reserve_final - reserve_midterm
        base, remainder = divmod(slots, count)
        groups = []
        for index, name in enumerate(topic_names):
            span = base + (1 if index < remainder else 0)
            groups.append([name])
            groups.extend([f"{name} (continued)"] for _ in range(span - 1))
        if reserve_midterm:
            groups.insert(len(groups) // 2, ["Midterm review and practice"])
        if reserve_final:
            groups.append(["Review and final assessment"])

    return [
        {"week": number, "topics": topics}
        for number, topics in enumerate(groups, start=1)
    ]


def build_schedule(description, weeks):
    """The /api/schedule entry point. Returns the response dict, including an
    'error' key when no usable curriculum could be assembled."""
    key = (" ".join(description.lower().split()), int(weeks))
    cached = _cache.get(key)
    if cached is not None:
        return cached

    query = analyze_description(description)
    mentions = extract_mentions(description)

    topics, citations, confidence = [], [], "low"
    if query.subject:
        pages = [(s, t, r, u, False) for s, t, r, u in _fetch_all(query)]
        if not any(harvest_items(raw, title) for _, title, raw, _, _ in pages):
            # Unlexiconed subject: find curriculum pages by search and trust
            # their whole page (we chose them deliberately).
            pages = [(s, t, r, u, True) for s, t, r, u in search_fallback_pages(query)]
        per_page_items, neutral = [], set()
        for source, title, raw, url, whole_page in pages:
            items = harvest_items(raw, title, whole_page=whole_page)
            if not items and whole_page:
                # No topic lists on this page — its section headings are
                # still a topical breakdown of the subject.
                headings = harvest_headings(raw)
                items = headings if len(headings) >= 3 else []
            if not items:
                continue
            if _is_alphabetical(items):
                # Catalog page: its ordering carries no pedagogy.
                neutral.add(len(citations) + 1)
            if len(items) > ALPHA_SAMPLE_TO:
                # A huge page (outline link lists) must contribute breadth,
                # not just its first section.
                items = _sample_evenly(items, ALPHA_SAMPLE_TO)
            citations.append({"title": title, "url": url, "source": source.name})
            per_page_items.append((len(citations), items))
        topics = _filter_topics(
            aggregate(per_page_items, neutral), citations, mentions
        )
        if len(topics) >= MIN_TOPICS:
            corroborating = {c for topic in topics for c in topic["citations"]}
            confidence = "high" if len(corroborating) >= 2 else "medium"
        else:
            topics, citations = [], []

    topics = _weave_mentions(topics, mentions)
    if not topics:
        return {
            "error": (
                "Couldn't identify the course subject or any required topics. "
                "Name the subject explicitly (e.g. 'an introductory Python "
                "programming course') or list topics with 'covering ...'."
            )
        }

    result = {
        "subject": query.subject or "Course",
        "weeks": allocate([t["name"] for t in topics], weeks),
        "topics": topics,
        "citations": citations,
        "confidence": confidence,
    }
    # A sourceless result for a known subject usually means the source APIs
    # failed (rate limit, outage) — don't poison the cache with it for an hour.
    if citations or not query.subject:
        _cache.set(key, result)
    return result
