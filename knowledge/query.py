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

# Filler that adds nothing to a search query or to confidence scoring.
VAGUE_WORDS = frozenset(
    """need needs needed want wants wanted get gets make makes use used using
    way ways thing things stuff best good great important really actually
    several many lot lots""".split()
)

# Words about the *shape* of the desired answer, not its subject. They stay in
# the ranking keywords (they boost sentences like "covers topics including:")
# but are excluded from API search strings, where they derail keyword search.
META_WORDS = frozenset(
    """topic topics concept concepts subject subjects area areas skill skills
    list lists cover covers covered covering include includes included""".split()
)

EDUCATION_TERMS = frozenset(
    """course courses curriculum syllabus class classes college university
    school teach teaching taught learn learning lesson lessons student
    students textbook beginner beginners introductory bootcamp""".split()
)

# Qualifiers that describe a course's level/importance, not its subject.
LEVEL_TERMS = frozenset(
    """college university school high undergraduate graduate beginner
    beginners introductory intro foundational core essential key main basic
    basics fundamental advanced""".split()
)

# Canonical subject names for deterministic curriculum lookups. Multi-word
# phrases are checked against the raw question; single tokens against tokens.
SUBJECT_PHRASES = {
    "cyber security": "Computer security",
    "cybersecurity": "Computer security",
    "computer security": "Computer security",
    "information security": "Computer security",
    "object oriented programming": "Object-oriented programming",
    "object-oriented programming": "Object-oriented programming",
    "computer programming": "Computer programming",
    "machine learning": "Machine learning",
    "data science": "Data science",
    "web development": "Web development",
    "web design": "Web design",
    "computer science": "Computer science",
    "artificial intelligence": "Artificial intelligence",
    "data structures": "Data structures",
    "operating systems": "Operating systems",
}
# Subjects whose own name has no curriculum page, but whose parent field
# does. Keyed by lowercase subject; value is the field whose curriculum to
# fetch alongside.
RELATED_CURRICULUM = {
    "ethical hacking": "Computer security",
    "hacking": "Computer security",
    "penetration testing": "Computer security",
    "network security": "Computer security",
    "digital forensics": "Computer security",
}

# Academic fields with Wikiversity/Wikipedia-outline coverage.
FIELD_SUBJECTS = {
    name: name.capitalize()
    for name in """psychology sociology history biology chemistry physics
    economics philosophy statistics calculus algebra anthropology astronomy
    geology geography accounting marketing finance microbiology genetics
    linguistics nutrition ethics logic botany ecology zoology literature
    music""".split()
}
SUBJECT_ALIASES = {
    "python": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "c++": "C++",
    "cpp": "C++",
    "c#": "C Sharp",
    "csharp": "C Sharp",
    "go": "Go",
    "golang": "Go",
    "ruby": "Ruby",
    "php": "PHP",
    "rust": "Rust",
    "swift": "Swift",
    "kotlin": "Kotlin",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
}

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
    qtype: str = "generic"          # definition | howto | why | person | list | generic
    is_programming: bool = False
    is_education: bool = False
    is_curriculum: bool = False     # "what topics does a X course cover"-shaped
    subject: str = ""               # canonical course subject, e.g. "Python"
    search_terms: str = ""          # what actually gets sent to source APIs


def tokenize(text):
    return re.findall(r"[a-zA-Z0-9#+]+", text.lower())


def stem(token):
    """Tiny suffix-stripping stemmer, enough to align question and source
    vocabulary for BM25. Deliberately conservative. The plural rules must be
    consistent with their singulars: "files" -> "file" (not "fil") so it
    matches "file"; "classes" -> "class"."""
    for suffix in ("ingly", "edly", "ing", "ies", "ied", "ed", "ly"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            base = token[: -len(suffix)]
            if suffix in ("ies", "ied"):
                return base + "y"
            return base
    if token.endswith(("xes", "zes", "ches", "shes", "sses")) and len(token) >= 5:
        return token[:-2]
    if token.endswith("s") and not token.endswith(("ss", "us", "is")) and len(token) >= 4:
        return token[:-1]
    return token


def content_tokens(text):
    """Stemmed tokens with stopwords removed — the BM25 vocabulary."""
    return [stem(t) for t in tokenize(text) if t not in STOPWORDS]


_LIST_NOUNS = r"(topics?|concepts?|subjects?|skills?|areas?|fundamentals|basics)"
_LIST_PATTERNS = [
    # list-noun anywhere near the start of a what/which question — catches
    # "what are the foundational topics ...", not just "what topics ..."
    rf"^(what|which)\b.{{0,40}}\b{_LIST_NOUNS}\b",
    r"^what\s+(should|needs?\s+to|must|has\s+to)\s+be\s+(taught|covered|included)",
    r"\b(syllabus|curriculum)\s+(for|of)\b",
    r"^what\s+(do|does|should|would)\b.*\b(course|class|curriculum)\b.*\bcover",
]


def classify(question):
    q = question.lower().strip()
    if any(re.search(p, q) for p in _LIST_PATTERNS) or "list of" in q:
        return "list"
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


def extract_subject(question, keywords):
    """Canonical course subject: known multi-word phrases first, then known
    single-token names, then whatever substantive keywords remain."""
    q = question.lower()
    for phrase, canonical in SUBJECT_PHRASES.items():
        if phrase in q:
            return canonical
    for token in tokenize(question):
        if token in SUBJECT_ALIASES:
            return SUBJECT_ALIASES[token]
    leftovers = [
        k
        for k in keywords
        if k not in VAGUE_WORDS
        and k not in META_WORDS
        and k not in EDUCATION_TERMS
        and k not in LEVEL_TERMS
    ]
    return " ".join(leftovers[:3]).capitalize() if leftovers else ""


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
    is_education = bool(tokens & EDUCATION_TERMS)
    is_curriculum = qtype == "list" and is_education
    subject = extract_subject(question, keywords) if is_curriculum else ""

    # Sources get a focused keyword query, not the raw question — long
    # natural-language strings derail keyword-based search APIs. A cleanly
    # stripped short topic ("cognitive dissonance") is even better.
    informative = [k for k in keywords if k not in VAGUE_WORDS and k not in META_WORDS]
    stripped = topic != question.strip().rstrip("?!. ").lower()
    if stripped and len(topic.split()) <= 5:
        search_terms = topic
    else:
        search_terms = " ".join(informative[:6]) or topic
        # Domain anchoring: "python college course" finds Monty Python on
        # Wikipedia; "python college course programming" finds Python.
        if is_programming and is_education and "programming" not in search_terms:
            search_terms += " programming"

    return AnalyzedQuery(
        raw=question.strip(),
        topic=topic,
        keywords=keywords,
        qtype=qtype,
        is_programming=is_programming,
        is_education=is_education,
        is_curriculum=is_curriculum,
        subject=subject,
        search_terms=search_terms,
    )
