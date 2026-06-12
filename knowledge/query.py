"""Question analysis: keyword extraction, topic isolation, question-type
classification. All rule-based — no models, no downloads."""

import re
from dataclasses import dataclass, field

STOPWORDS = frozenset(
    """a an the and or but if then else when while of in on at to from by for
    with about into through during before after above below up down out off
    over under again further once here there all any both each few more most
    other some such no nor not only own same so than too very can will just
    should now is are was were be been being have has had having do does did
    doing would could may might must shall this that these those i me my we
    our you your he him his she her it its they them their what which who
    whom whose where why how""".split()
)

# Words that carry question intent but no topical content.
QUESTION_WORDS = frozenset(
    """what who whom whose which where when why how define definition meaning
    mean means explain describe tell work works working caused causes cause
    happen happens happened difference between""".split()
)

_PREFIX_PATTERNS = [
    r"^(what|who)\s+(is|are|was|were)\s+(a|an|the)?\s*",
    r"^what\s+does\s+",
    r"^what\s+do\s+",
    r"^(define|definition\s+of|meaning\s+of|explain|describe)\s+",
    r"^how\s+(do|does|can|could|should|would)\s+(i|you|we|one)?\s*",
    r"^how\s+to\s+",
    r"^why\s+(is|are|was|were|do|does|did)\s+",
    r"^(can|could|should|would)\s+(i|you|we|one)\s+",
    r"^tell\s+me\s+about\s+",
]

_SUFFIX_PATTERNS = [r"\s+mean\??$", r"\s+work\??$", r"\s+works\??$"]

_PROGRAMMING_TERMS = frozenset(
    """python javascript typescript java kotlin swift rust golang ruby php
    perl scala haskell sql nosql html css flask django react angular vue
    node nodejs npm pip git docker kubernetes api rest json xml yaml regex
    function method class variable array list dict dictionary string integer
    boolean loop recursion pointer thread async await promise callback
    closure decorator lambda iterator generator exception error traceback
    stacktrace compile compiler interpreter runtime syntax debug debugger
    library framework module package import export database query index
    server client frontend backend algorithm dataframe pandas numpy tensor
    bash shell terminal linux unix windows ide vscode github bug code
    coding programming software""".split()
)

_CODE_PATTERN = re.compile(
    r"[a-z]+[A-Z][a-zA-Z]*"        # camelCase
    r"|\w+_\w+"                     # snake_case
    r"|\w+\(\)"                     # call()
    r"|::|->|=>|</?\w+>"            # operators / tags
)


@dataclass
class AnalyzedQuery:
    raw: str
    topic: str                      # question with interrogative scaffolding stripped
    keywords: list = field(default_factory=list)
    qtype: str = "generic"          # definition | howto | why | person | generic
    is_programming: bool = False


def tokenize(text):
    return re.findall(r"[a-zA-Z0-9#+]+", text.lower())


def stem(token):
    """Tiny suffix-stripping stemmer, enough to align question and source
    vocabulary for BM25. Deliberately conservative."""
    for suffix in ("ingly", "edly", "ing", "ies", "ied", "ed", "ly", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            base = token[: -len(suffix)]
            if suffix == "ies" or suffix == "ied":
                return base + "y"
            return base
    return token


def content_tokens(text):
    """Stemmed tokens with stopwords removed — the BM25 vocabulary."""
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS]


def classify(question):
    q = question.lower().strip()
    if re.search(r"^(what\s+(is|are|was|were)|define|definition\s+of|meaning\s+of)\b", q) or re.search(
        r"^what\s+does\b.*\bmean", q
    ):
        return "definition"
    if re.search(r"^how\b", q):
        return "howto"
    if re.search(r"^why\b", q):
        return "why"
    if re.search(r"^who\b", q):
        return "person"
    return "generic"


def extract_topic(question):
    topic = question.strip().rstrip("?!. ").lower()
    for pattern in _PREFIX_PATTERNS:
        new = re.sub(pattern, "", topic, count=1)
        if new != topic:
            topic = new
            break
    for pattern in _SUFFIX_PATTERNS:
        topic = re.sub(pattern, "", topic, count=1)
    return topic.strip() or question.strip().rstrip("?!. ")


def analyze(question):
    qtype = classify(question)
    topic = extract_topic(question)
    keywords = []
    for token in tokenize(question):
        if token in STOPWORDS or token in QUESTION_WORDS:
            continue
        if token not in keywords:
            keywords.append(token)
    if not keywords:
        keywords = tokenize(topic)

    tokens = set(tokenize(question))
    is_programming = bool(tokens & _PROGRAMMING_TERMS) or bool(
        _CODE_PATTERN.search(question)
    )
    return AnalyzedQuery(
        raw=question.strip(),
        topic=topic,
        keywords=keywords,
        qtype=qtype,
        is_programming=is_programming,
    )
