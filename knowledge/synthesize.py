"""Extractive synthesis: choose the best non-redundant sentences, order them
coherently, group into paragraphs, and attach numbered citations."""

import re

from .query import content_tokens

MAX_SENTENCES = 7
JACCARD_DUPLICATE = 0.55

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


def _jaccard(a, b):
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _dedupe(sentences):
    kept = []
    for sentence in sentences:
        if any(_jaccard(sentence.tokens, k.tokens) > JACCARD_DUPLICATE for k in kept):
            continue
        kept.append(sentence)
    return kept


def _order(sentences, query):
    """Open with a definition-shaped sentence, preferring one from the passage
    whose title best matches the question topic (so the main article on a
    subject beats tangent articles that merely mention it a lot)."""
    topic = set(content_tokens(query.topic))

    def opener_rank(sentence):
        title = set(content_tokens(sentence.passage.title))
        overlap = len(topic & title) / len(topic | title) if topic and title else 0.0
        shaped = bool(_DEFINITION_OPENER.match(sentence.text))
        return (round(overlap, 2), shaped, sentence.score)

    opener = max(sentences, key=opener_rank)
    if not _DEFINITION_OPENER.match(opener.text):
        return sentences
    rest = [s for s in sentences if s is not opener]
    return [opener] + rest


def _confidence(selected, query):
    if not selected:
        return "none"
    covered = set()
    needed = {token for keyword in query.keywords for token in [keyword.lower()]}
    if not needed:
        return "low"
    for sentence in selected:
        text = sentence.text.lower()
        covered |= {term for term in needed if term in text}
    coverage = len(covered) / len(needed)
    if coverage >= 0.7 and len(selected) >= 3:
        return "high"
    if coverage >= 0.4:
        return "medium"
    return "low"


def synthesize(query, ranked_sentences):
    """ranked_sentences: ScoredSentence list, best-first. Returns the response
    dict served by /api/ask."""
    candidates = [s for s in ranked_sentences if s.score > 0][: MAX_SENTENCES * 3]
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
