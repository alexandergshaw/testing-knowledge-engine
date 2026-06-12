"""BM25 sentence ranking. Hand-rolled (~40 lines) so the only runtime
dependency for scoring is the standard library."""

import math
import re
from collections import Counter
from dataclasses import dataclass

from .query import content_tokens

_ABBREVIATIONS = r"(?<!\be\.g)(?<!\bi\.e)(?<!\betc)(?<!\bvs)(?<!\bDr)(?<!\bMr)(?<!\bMs)(?<!\bSt)(?<!\bno)"
_SENTENCE_SPLIT = re.compile(_ABBREVIATIONS + r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")

MIN_SENTENCE_CHARS = 30
MAX_SENTENCE_CHARS = 500
LEAD_SENTENCE_BOOST = 1.25
TITLE_MATCH_WEIGHT = 0.5


def _title_boost(query, passage):
    """Prefer passages whose title matches the question topic — Jaccard so
    'Cognitive dissonance' beats 'Vicarious cognitive dissonance'."""
    topic = set(content_tokens(query.topic))
    title = set(content_tokens(passage.title))
    if not topic or not title:
        return 1.0
    return 1.0 + TITLE_MATCH_WEIGHT * len(topic & title) / len(topic | title)


@dataclass
class ScoredSentence:
    text: str
    tokens: list
    passage: object   # the Passage this sentence came from
    score: float = 0.0


class BM25:
    def __init__(self, corpus, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.doc_freqs = [Counter(doc) for doc in corpus]
        self.doc_lens = [len(doc) for doc in corpus]
        n_docs = len(corpus)
        self.avgdl = (sum(self.doc_lens) / n_docs) if n_docs else 0.0
        df = Counter()
        for doc in corpus:
            df.update(set(doc))
        self.idf = {
            term: math.log(1 + (n_docs - n + 0.5) / (n + 0.5))
            for term, n in df.items()
        }

    def score(self, query_tokens, index):
        freqs = self.doc_freqs[index]
        length = self.doc_lens[index]
        norm = 1 - self.b + self.b * length / (self.avgdl or 1)
        total = 0.0
        for term in query_tokens:
            freq = freqs.get(term, 0)
            if not freq:
                continue
            total += self.idf.get(term, 0) * freq * (self.k1 + 1) / (freq + self.k1 * norm)
        return total


def split_sentences(text):
    sentences = []
    for raw in _SENTENCE_SPLIT.split(text):
        sentence = raw.strip()
        if MIN_SENTENCE_CHARS <= len(sentence) <= MAX_SENTENCE_CHARS:
            sentences.append(sentence)
    return sentences


def rank(query, passages):
    """Score every sentence in every passage against the question and return
    ScoredSentence list sorted best-first."""
    sentences = []
    for passage in passages:
        for position, text in enumerate(split_sentences(passage.text)):
            tokens = content_tokens(text)
            if len(tokens) < 4:
                continue
            sentences.append(
                ScoredSentence(text=text, tokens=tokens, passage=passage)
            )
            sentences[-1].lead = position == 0
    if not sentences:
        return []

    bm25 = BM25([s.tokens for s in sentences])
    query_tokens = content_tokens(" ".join(query.keywords) or query.topic)
    title_boosts = {id(p): _title_boost(query, p) for p in passages}
    for index, sentence in enumerate(sentences):
        score = (
            bm25.score(query_tokens, index)
            * sentence.passage.trust
            * title_boosts[id(sentence.passage)]
        )
        if getattr(sentence, "lead", False):
            score *= LEAD_SENTENCE_BOOST
        sentence.score = score

    return sorted(sentences, key=lambda s: s.score, reverse=True)
