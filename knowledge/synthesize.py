"""Extractive synthesis: choose the best non-redundant sentences, order them
coherently, group into paragraphs, and attach numbered citations."""

import re

from .query import VAGUE_WORDS, content_tokens

MAX_SENTENCES = 7
JACCARD_DUPLICATE = 0.55
# Sentences scoring far below the best match are tangents, not support —
# a shorter answer beats a padded one. List questions are held to a stricter
# bar: the enumeration is the answer, padding only dilutes it.
MIN_RELATIVE_SCORE = 0.2
MIN_RELATIVE_SCORE_LIST = 0.4

FALLBACK_ANSWER = (
    "I couldn't find solid information on that in my trusted sources. "
    "Try rephrasing the question or using more specific terms."
)

# "Definition-shaped": a copular verb within the first ~8 tokens. Loose on its
# own, but the opener picker pairs it with title-topic overlap, which is what
# actually selects the right article.
_DEFINITION_OPENER = re.compile(
    r"^\W*(?:\S+\s+){0,8}(?:is|are|was|were|refers to|describes|denotes)\s",
    re.IGNORECASE,
)


def sanitize_layman(text):
    """Strip encyclopedic markup that leaks into extracted prose — LaTeX
    (`{\\displaystyle O(n)}`), stray TeX commands, leftover braces, and the
    spaces around inner parentheses ('O ( n )' -> 'O(n)')."""
    text = re.sub(r"\{\\displaystyle[^{}]*\}", "", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = re.sub(r"\{[^{}]*\}", "", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def jaccard(a, b):
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _dedupe(sentences):
    kept = []
    for sentence in sentences:
        if any(jaccard(sentence.tokens, k.tokens) > JACCARD_DUPLICATE for k in kept):
            continue
        kept.append(sentence)
    return kept


_LIST_OPENER = re.compile(
    r"\bcovers topics including\b|\btopics include\b|\bcomprises\b", re.IGNORECASE
)


def _order(sentences, query):
    """Open with a definition-shaped sentence, preferring one from the passage
    whose title best matches the question topic (so the main article on a
    subject beats tangent articles that merely mention it a lot). List
    questions open with an enumeration when one was retrieved."""
    if query.qtype == "list":
        for sentence in sentences:  # already best-first
            if _LIST_OPENER.search(sentence.text):
                return [sentence] + [s for s in sentences if s is not sentence]

    # How/why questions want the best explanation first, not a definition of
    # the surrounding concept — keep score order.
    if query.qtype in ("howto", "why"):
        return sentences

    topic = set(content_tokens(query.topic))

    def opener_rank(sentence):
        title = set(content_tokens(sentence.passage.title))
        overlap = len(topic & title) / len(topic | title) if topic and title else 0.0
        shaped = bool(_DEFINITION_OPENER.match(sentence.text))
        return (round(overlap, 2), shaped, sentence.score)

    # Title overlap alone can't crown the opener — a demoted passage (e.g. a
    # film sharing the topic's exact name) may have perfect overlap but a
    # poor score. Only strong sentences are opener candidates.
    pool = [s for s in sentences if s.score >= 0.5 * sentences[0].score]
    opener = max(pool, key=opener_rank)
    if not _DEFINITION_OPENER.match(opener.text):
        return sentences
    rest = [s for s in sentences if s is not opener]
    return [opener] + rest


def _confidence(selected, query):
    if not selected:
        return "none"
    # Stemmed comparison ("covered" matches "covers"), filler words excluded.
    substantive = [k for k in query.keywords if k not in VAGUE_WORDS]
    needed = set(content_tokens(" ".join(substantive)))
    if not needed:
        return "low"
    covered = set()
    for sentence in selected:
        covered |= needed & set(sentence.tokens)
    coverage = len(covered) / len(needed)
    if coverage >= 0.7 and len(selected) >= 3:
        return "high"
    if coverage >= 0.4:
        return "medium"
    return "low"


def synthesize(query, ranked_sentences):
    """ranked_sentences: ScoredSentence list, best-first. Returns the response
    dict served by /api/ask."""
    relative = MIN_RELATIVE_SCORE_LIST if query.qtype == "list" else MIN_RELATIVE_SCORE
    floor = ranked_sentences[0].score * relative if ranked_sentences else 0
    candidates = [s for s in ranked_sentences if s.score > 0 and s.score >= floor]
    candidates = candidates[: MAX_SENTENCES * 3]
    selected = _dedupe(candidates)[:MAX_SENTENCES]
    confidence = _confidence(selected, query)

    if not selected or confidence == "none":
        return {"answer": FALLBACK_ANSWER, "citations": [], "confidence": "none"}

    ordered = _order(selected, query)

    # Number citations by first appearance.
    citations, citation_index = [], {}
    for sentence in ordered:
        key = (sentence.passage.title, sentence.passage.url)
        if key not in citation_index:
            citation_index[key] = len(citations) + 1
            citations.append(
                {
                    "title": sentence.passage.title,
                    "url": sentence.passage.url,
                    "source": sentence.passage.source,
                }
            )

    # Assemble paragraphs: lead paragraph of up to 3 sentences, rest follows.
    # A citation marker is emitted whenever the source changes or a paragraph ends.
    split_at = 3 if len(ordered) > 3 else len(ordered)
    paragraphs, current = [], []
    for position, sentence in enumerate(ordered):
        number = citation_index[(sentence.passage.title, sentence.passage.url)]
        next_number = (
            citation_index[
                (ordered[position + 1].passage.title, ordered[position + 1].passage.url)
            ]
            if position + 1 < len(ordered)
            else None
        )
        end_of_paragraph = position == split_at - 1 or position == len(ordered) - 1
        text = sentence.text
        if number != next_number or end_of_paragraph:
            text += f" [{number}]"
        current.append(text)
        if end_of_paragraph:
            paragraphs.append(" ".join(current))
            current = []

    return {
        "answer": "\n\n".join(paragraphs),
        "citations": citations,
        "confidence": confidence,
    }
