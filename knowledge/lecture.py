"""Module objectives -> a PowerPoint lecture. For each learning objective the
deck carries an explanation slide (extractively synthesized from trusted
sources) and worked-example slide(s) with talking points in the speaker notes.
No LLM: every word is retrieved and cited.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .cache import TTLCache
from .pipeline import fetch, select_sources
from .query import (
    _CODE_PATTERN,
    _PROGRAMMING_TERMS,
    STOPWORDS,
    SUBJECT_ALIASES,
    analyze,
    tokenize,
)
from .ranking import rank, split_sentences
from .slides import (
    add_bullet_slide,
    add_code_box,
    add_content_slide,
    add_list_slide,
    add_text_box,
    add_title_slide,
    deck_bytes,
    new_deck,
    set_notes,
)
from .synthesize import FALLBACK_ANSWER, synthesize

log = logging.getLogger(__name__)

MAX_OBJECTIVES = 20
MAX_POINTS_PER_SLIDE = 6
MAX_EXAMPLES_PER_OBJECTIVE = 2
MAX_CONCEPT_SLIDES = 15
MAX_CODE_LINES = 14
TITLE_SHORT_LIMIT = 55

_cache = TTLCache(ttl_seconds=3600)
_concept_cache = TTLCache(ttl_seconds=3600)


class LectureError(ValueError):
    """User-facing problem with the objectives input."""


# --- objective parsing -------------------------------------------------------

# Bloom's-taxonomy action verbs — objectives almost always begin with one,
# which lets us segment run-on prose like "define X, explain Y, and apply Z".
BLOOM_VERBS = frozenset(
    """define describe explain identify list apply analyze analyse evaluate
    create compare demonstrate calculate implement design discuss summarize
    summarise interpret classify outline illustrate distinguish examine relate
    predict solve construct develop differentiate recognize recognise state
    name label recall understand use write build model derive prove formulate
    assess select compute draw measure perform produce review organize
    organise plan test debug deploy configure choose provide give determine
    show find write read""".split()
)

# Only strip a real preamble: "...will be able to[:]" / "...will learn[:]", or a
# header word that ends in a colon. Anchored so a bare "outcomes" inside an
# objective ("evaluate learning outcomes") is never mistaken for a lead-in.
_LEAD_IN = re.compile(
    r"^.*?\bwill\s+(?:be\s+able\s+to|learn(?:\s+to)?)\s*:?\s+"
    r"|^\s*(?:objectives?|goals?|outcomes?|aims?|students?\s+will)\s*:\s*",
    re.IGNORECASE,
)
_MARKER_COUNT = re.compile(r"(?:^|\s)(?:\(?\d+[.)]|[-*•–])\s")
_MARKER_SPLIT = re.compile(r"(?:^|\s)(?:\(?\d+[.)]|[-*•–])\s+")
_CLAUSE_SPLIT = re.compile(r"\s*(?:[;\n]|,|\band\b|(?<=[.!?])\s)\s*", re.IGNORECASE)


def _strip_lead_in(text):
    """Drop a leading 'students will be able to:'-style preamble, if any sits
    near the front."""
    match = _LEAD_IN.search(text[:200])
    return text[match.end() :] if match else text


def _split_on_verbs(text):
    """Segment so each objective begins at an action verb; fragments that don't
    start with a verb are continuations of the previous objective."""
    fragments = [f.strip(" .;,") for f in _CLAUSE_SPLIT.split(text) if f.strip(" .;,")]
    objectives = []
    for fragment in fragments:
        first = re.match(r"[a-zA-Z]+", fragment)
        if first and first.group(0).lower() in BLOOM_VERBS:
            objectives.append(fragment)
        elif objectives:
            objectives[-1] = f"{objectives[-1]}, {fragment}"
        else:
            objectives.append(fragment)
    return objectives


def _finalize(items, limit):
    seen, out = set(), []
    for item in items:
        objective = re.sub(
            r"^(?:be\s+able\s+to|able\s+to|to)\s+", "", item.strip(" .;:-*•–"), flags=re.IGNORECASE
        )
        objective = re.sub(r"\s+", " ", objective).strip()
        key = objective.lower()
        if objective and key not in seen:
            seen.add(key)
            out.append(objective)
        if len(out) >= limit:
            break
    return out


def parse_objectives(text, limit=MAX_OBJECTIVES):
    """Extract distinct objectives from free-form text, format-agnostic.
    Cascade (first match wins): explicit markers -> multi-line -> lead-in/prose
    verb segmentation -> sentence split -> single objective."""
    text = (text or "").strip()
    if not text:
        return []

    if len(_MARKER_COUNT.findall(text)) >= 2:
        return _finalize(_MARKER_SPLIT.split(text), limit)

    body = _strip_lead_in(text)

    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if len(lines) >= 2:
        return _finalize(lines, limit)

    verb_items = _split_on_verbs(body)
    if len(verb_items) >= 2:
        return _finalize(verb_items, limit)

    sentences = split_sentences(body)
    if len(sentences) >= 2:
        return _finalize(sentences, limit)

    return _finalize([body], limit)


# --- per-objective content ---------------------------------------------------

_EXAMPLE_MARKERS = re.compile(
    r"\b(for example|for instance|e\.?g\.?|such as|consider|suppose|imagine|"
    r"to illustrate|as an example|say you)\b",
    re.IGNORECASE,
)


@dataclass
class ObjectiveResult:
    objective: str
    points: list = field(default_factory=list)            # explanation bullets
    examples: list = field(default_factory=list)          # prose/code (non-programming lectures)
    concept_examples: list = field(default_factory=list)  # per-concept code (programming lectures)
    citations: list = field(default_factory=list)
    confidence: str = "none"


def _code_lines(block):
    lines = [line.rstrip() for line in block.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines[:MAX_CODE_LINES]


# Concrete code constructs/skills you would actually show code FOR. A topic
# that merely names a language ("history of Python") is NOT one of these, so it
# won't get a code example slide even though it's programming-flagged.
_CODE_CONSTRUCTS = frozenset(
    """loop loops function functions method methods variable variables array
    arrays list lists dict dictionary dictionaries set sets tuple tuples string
    strings class classes object objects inheritance polymorphism encapsulation
    recursion pointer pointers thread threads async await promise callback
    closure decorator decorators lambda iterator iterators generator generators
    exception exceptions error errors syntax regex query join api json xml file
    files io algorithm algorithms compile compiler debugging conditional
    conditionals operator operators expression expressions statement statements
    parameter parameters argument arguments boolean integer float""".split()
)


def _deals_with_code(query):
    """True only when the objective names an actual code construct/skill (or
    contains code syntax) — not merely a language name or a meta/historical
    aspect of programming."""
    tokens = {tokenize(token)[0] for token in query.keywords if tokenize(token)}
    tokens |= set(tokenize(query.raw))
    return bool(tokens & _CODE_CONSTRUCTS) or bool(_CODE_PATTERN.search(query.raw))


# Construct words -> a canonical, teachable concept name. Each concept the
# lecture covers gets its own code example slide.
CONCEPT_CANON = {}


def _register_concept(words, canonical):
    for word in words.split():
        CONCEPT_CANON[word] = canonical


_register_concept("variable variables", "Variables")
_register_concept("function functions method methods", "Functions")
_register_concept("loop loops iteration iterating", "Loops")
_register_concept("conditional conditionals branching", "Conditionals")
_register_concept("list lists array arrays", "Lists & Arrays")
_register_concept("dict dictionary dictionaries hashmap", "Dictionaries")
_register_concept("set sets", "Sets")
_register_concept("tuple tuples", "Tuples")
_register_concept("string strings", "Strings")
_register_concept("class classes object objects oop", "Classes & Objects")
_register_concept("inheritance polymorphism encapsulation", "Object-Oriented Design")
_register_concept("recursion recursive", "Recursion")
_register_concept("exception exceptions error errors", "Exceptions & Errors")
_register_concept("file files io", "File I/O")
_register_concept("regex", "Regular Expressions")
_register_concept("decorator decorators", "Decorators")
_register_concept("generator generators", "Generators")
_register_concept("lambda lambdas", "Lambdas")
_register_concept("closure closures", "Closures")
_register_concept("pointer pointers", "Pointers")
_register_concept("thread threads async await concurrency", "Concurrency")
_register_concept("operator operators", "Operators")
_register_concept("boolean booleans", "Booleans")


# Multi-word concepts single-token matching would miss ("control structures",
# "data types"). Checked against the raw text before single tokens.
CONCEPT_PHRASES = {
    "control structures": "Control Structures",
    "control structure": "Control Structures",
    "control flow": "Control Structures",
    "data types": "Data Types",
    "data type": "Data Types",
    "numeric types": "Data Types",
    "primitive types": "Data Types",
    "data structures": "Data Structures",
    "data structure": "Data Structures",
    "object oriented": "Classes & Objects",
    "object-oriented": "Classes & Objects",
    "error handling": "Exceptions & Errors",
    "exception handling": "Exceptions & Errors",
    "regular expressions": "Regular Expressions",
    "regular expression": "Regular Expressions",
    "file handling": "File I/O",
}


def extract_concepts(query):
    """Ordered, de-duplicated canonical programming concepts named in an
    objective's text — multi-word ('control structures', 'data types') and
    single-word ('conditionals and loops' -> [Conditionals, Loops])."""
    text = query.raw.lower()
    found = []
    for phrase, canonical in CONCEPT_PHRASES.items():
        position = text.find(phrase)
        if position >= 0:
            found.append((position, canonical))
    for match in re.finditer(r"[a-zA-Z0-9#+]+", text):
        canonical = CONCEPT_CANON.get(match.group(0))
        if canonical:
            found.append((match.start(), canonical))

    seen, concepts = set(), []
    for _, canonical in sorted(found, key=lambda item: item[0]):
        if canonical not in seen:
            seen.add(canonical)
            concepts.append(canonical)
    return concepts


def _infer_language(objectives, title):
    """The course's programming language (for concept code searches), from the
    title + objectives. '' when none is named."""
    for token in tokenize(f"{title} {' '.join(objectives)}"):
        if token in SUBJECT_ALIASES and token not in {"go", "r"}:
            return SUBJECT_ALIASES[token]
    return ""


def _first_code(passages, ranked):
    """First usable code block, preferring passages backing the top-ranked
    sentences. Returns (lines, passage) or (None, None)."""
    ordered, seen = [], set()
    for passage in [s.passage for s in ranked] + list(passages):
        if id(passage) not in seen:
            seen.add(id(passage))
            ordered.append(passage)
    for passage in ordered:
        for block in passage.code or []:
            lines = _code_lines(block)
            if lines:
                return lines, passage
    return None, None


def _concept_code(concept, language):
    """A captioned code example for a single concept, retrieved on a focused
    '<language> <concept> example' query. Cached by (concept, language); returns
    None when no pertinent code is found."""
    key = (concept.lower(), language.lower())
    cached = _concept_cache.get(key)
    if cached is not None:
        return cached[0]

    query = analyze(f"{language} {concept} example".strip())
    # A concept is a programming idea by construction — force Stack Overflow into
    # the source set even if the short query string doesn't trip is_programming.
    query.is_programming = True
    result = None
    try:
        passages = fetch(query, select_sources(query))
        ranked = rank(query, passages) if passages else []
        lines, passage = _first_code(passages, ranked)
        if lines:
            result = {
                "kind": "code",
                "concept": concept,
                "text": _best_example_text(ranked) or f"A worked {concept.lower()} example.",
                "lines": lines,
                "title": passage.title,
                "url": passage.url,
                "source": passage.source,
            }
    except Exception:
        log.warning("concept code fetch failed: %s", concept, exc_info=True)
    _concept_cache.set(key, (result,))  # cache misses too, to avoid re-fetching
    return result


def _best_example_text(ranked):
    """A self-contained sentence to caption a code example — a 'for example…'
    sentence if one exists, otherwise the top-ranked explanation."""
    for sentence in ranked:
        if _EXAMPLE_MARKERS.search(sentence.text):
            return sentence.text
    return ranked[0].text if ranked else ""


def _code_examples(query, passages, ranked, limit):
    """Code-block examples (topics that actually deal with code), each captioned
    with a pertinent explanatory sentence so the slide carries words AND code.
    Code is taken preferentially from the passages backing the top-ranked
    sentences."""
    if not _deals_with_code(query):
        return []
    caption = _best_example_text(ranked)
    ordered, seen = [], set()
    for passage in [s.passage for s in ranked] + list(passages):
        if id(passage) not in seen:
            seen.add(id(passage))
            ordered.append(passage)

    examples = []
    for passage in ordered:
        for block in passage.code or []:
            lines = _code_lines(block)
            if lines:
                examples.append(
                    {
                        "kind": "code",
                        "text": caption,
                        "lines": lines,
                        "title": passage.title,
                        "url": passage.url,
                        "source": passage.source,
                    }
                )
                break
        if len(examples) >= limit:
            break
    return examples


def extract_examples(
    query, passages, ranked, programming_lecture=False, limit=MAX_EXAMPLES_PER_OBJECTIVE
):
    """Worked examples for an objective.

    Programming lecture: examples are driven per-concept elsewhere (see
    `_attach_concept_examples`), so this returns []. Otherwise: code (if any) +
    'for example…' prose + a best-effort fallback sentence."""
    if programming_lecture:
        return []

    examples = _code_examples(query, passages, ranked, limit)
    for sentence in ranked:
        if len(examples) >= limit:
            break
        if _EXAMPLE_MARKERS.search(sentence.text):
            examples.append(
                {
                    "kind": "prose",
                    "text": sentence.text,
                    "title": sentence.passage.title,
                    "url": sentence.passage.url,
                    "source": sentence.passage.source,
                }
            )

    if not examples and ranked:
        top = ranked[0]
        examples.append(
            {
                "kind": "prose",
                "text": top.text,
                "fallback": True,
                "title": top.passage.title,
                "url": top.passage.url,
                "source": top.passage.source,
            }
        )
    return examples[:limit]


def _to_points(answer):
    if not answer or answer == FALLBACK_ANSWER:
        return []
    text = re.sub(r"\s*\[\d+\]", "", answer)
    points = split_sentences(text)
    return (points or [text])[:MAX_POINTS_PER_SLIDE]


# Generic words in a module title that don't help disambiguate a topic.
_CONTEXT_STOPWORDS = STOPWORDS | frozenset(
    """intro introduction introductory module unit course lecture class lesson
    basics fundamentals overview principles essentials advanced beginner
    beginners""".split()
)


def context_terms(title):
    """Salient words from the module title, used to bias each objective's search
    toward the module's domain — so "for loop" in an "Intro to Python" module
    retrieves the programming sense, not a musical called 'A Strange Loop'."""
    if not title:
        return ""
    return " ".join(t for t in tokenize(title) if t not in _CONTEXT_STOPWORDS)


def is_programming_lecture(objectives, title=""):
    """The lecture is 'programming' when most objectives are code-flagged or the
    title names a programming language/term — used to gate example slides to
    code topics only."""
    queries = [analyze(objective) for objective in objectives]
    return sum(q.is_programming for q in queries) * 2 >= len(objectives) or bool(
        set(tokenize(title)) & _PROGRAMMING_TERMS
    )


def _build_objective(objective, context="", programming_lecture=False):
    query = analyze(objective)
    if context:
        # Bias retrieval without changing the slide's objective text.
        query.search_terms = f"{query.search_terms} {context}".strip()
    passages = fetch(query, select_sources(query))
    if not passages:
        return ObjectiveResult(objective)
    ranked = rank(query, passages)
    synth = synthesize(query, ranked)
    return ObjectiveResult(
        objective=objective,
        points=_to_points(synth["answer"]),
        examples=extract_examples(query, passages, ranked, programming_lecture),
        citations=synth["citations"],
        confidence=synth["confidence"],
    )


def _safe_build(objective, context="", programming_lecture=False):
    try:
        return _build_objective(objective, context, programming_lecture)
    except Exception:
        log.warning("objective failed: %s", objective, exc_info=True)
        return ObjectiveResult(objective)


# --- deck assembly -----------------------------------------------------------


def _short(text):
    text = text.strip()
    if len(text) <= TITLE_SHORT_LIMIT:
        return text
    return text[: TITLE_SHORT_LIMIT - 1].rstrip() + "…"


def _ref_key(item):
    return (item.get("title", ""), item.get("url", ""), item.get("source", ""))


def _explanation_notes(index, result):
    lines = [f"Objective {index}: {result.objective}", ""]
    if result.confidence in ("low", "none"):
        lines.append(
            f"(Source confidence: {result.confidence} — supplement this with your own material.)"
        )
    if result.citations:
        lines.append(
            "Sources: "
            + "; ".join(f"{c['title']} ({c['source']})" for c in result.citations)
        )
    return "\n".join(lines).strip()


def _example_notes(example):
    lines = ["Talking points:"]
    if example.get("fallback"):
        lines.append(
            "(No explicit example was found in the sources — this is the most "
            "relevant explanation; add a worked example of your own.)"
        )
    if example["kind"] == "code":
        lines.append("Walk through the code line by line and tie it back to the objective.")
    else:
        lines.append(example["text"])
    source = f"{example.get('title', '')} ({example.get('source', '')})"
    if example.get("url"):
        source += f" — {example['url']}"
    lines.append("Source: " + source)
    return "\n".join(lines).strip()


def build_module_deck(title, results):
    deck = new_deck()
    footer = title or "Module Lecture"
    add_title_slide(deck, title or "Module Lecture", f"{len(results)} learning objectives")

    # Agenda is reference material, not teaching bullets -> compact list slide.
    add_list_slide(
        deck,
        "Objectives",
        [f"{i}. {result.objective[:1].upper() + result.objective[1:]}" for i, result in enumerate(results, 1)],
        footer=footer,
    )

    refs, ref_order = {}, []

    def register(item):
        key = _ref_key(item)
        if key[0] and key not in refs:
            refs[key] = len(refs) + 1
            ref_order.append(item)

    for index, result in enumerate(results, 1):
        points = result.points or [
            "No reliable source was found for this objective — try rephrasing it "
            "or supplement from your own materials."
        ]
        # The two strongest points show on the slide; the rest land in notes.
        add_bullet_slide(
            deck,
            f"Objective {index}: {_short(result.objective)}",
            points,
            notes=_explanation_notes(index, result),
            footer=footer,
        )
        for citation in result.citations:
            register(citation)

        # Programming lecture: one code example slide per concept this objective
        # introduces (words + code).
        for example in result.concept_examples:
            concept_slide = add_content_slide(
                deck, f"Example: {example['concept']}", footer=footer
            )
            add_text_box(
                concept_slide,
                example.get("text") or f"A worked {example['concept'].lower()} example.",
                top=1.5,
                height=1.5,
                size=18,
            )
            add_code_box(concept_slide, example["lines"], top=3.2)
            set_notes(concept_slide, _example_notes(example))
            register(example)

        for example in result.examples:
            example_slide = add_content_slide(
                deck, f"Example — {_short(result.objective)}", footer=footer
            )
            if example["kind"] == "code":
                # Words + code: explain the example, then show the code beneath.
                add_text_box(
                    example_slide,
                    example.get("text") or "Worked example:",
                    top=1.5,
                    height=1.5,
                    size=18,
                )
                add_code_box(example_slide, example["lines"], top=3.2)
            else:
                add_text_box(example_slide, example["text"], top=1.6, height=4.0, size=20)
            set_notes(example_slide, _example_notes(example))
            register(example)

    if ref_order:
        add_list_slide(
            deck,
            "References",
            [f"[{refs[_ref_key(item)]}] {item['title']} — {item['source']}" for item in ref_order],
            footer=footer,
        )
    return deck_bytes(deck)


def _attach_concept_examples(results, objectives, title):
    """Give each programming concept the lecture covers its own code example,
    attached to the first objective that introduces it (de-duplicated). Concept
    code is fetched concurrently and cached."""
    language = _infer_language(objectives, title)
    owner, order = {}, []
    for result in results:
        for concept in extract_concepts(analyze(result.objective)):
            if concept not in owner:
                owner[concept] = result
                order.append(concept)
        if len(order) >= MAX_CONCEPT_SLIDES:
            break
    order = order[:MAX_CONCEPT_SLIDES]
    if not order:
        return
    with ThreadPoolExecutor(max_workers=min(len(order), 6)) as executor:
        examples = list(executor.map(lambda concept: _concept_code(concept, language), order))
    for concept, example in zip(order, examples):
        if example:
            owner[concept].concept_examples.append(example)


def build_lecture_deck(objectives_text, title="Module Lecture"):
    """The /api/v1/lecture entry point: returns (pptx_bytes, summary)."""
    objectives = parse_objectives(objectives_text)
    if not objectives:
        raise LectureError("No learning objectives found in the provided text.")

    title = (title or "Module Lecture").strip() or "Module Lecture"
    cache_key = (title.lower(), tuple(o.lower() for o in objectives))
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    # A programming lecture restricts example slides to code topics (with code).
    programming_lecture = is_programming_lecture(objectives, title)

    context = context_terms(title) if title != "Module Lecture" else ""
    with ThreadPoolExecutor(max_workers=min(len(objectives), 6)) as executor:
        results = list(
            executor.map(lambda o: _safe_build(o, context, programming_lecture), objectives)
        )

    if programming_lecture:
        _attach_concept_examples(results, objectives, title)

    payload = build_module_deck(title, results)
    summary = {
        "title": title,
        "objectives": len(objectives),
        "items": [
            {
                "objective": r.objective,
                "confidence": r.confidence,
                "examples": len(r.examples) + len(r.concept_examples),
            }
            for r in results
        ],
    }
    self_result = (payload, summary)
    _cache.set(cache_key, self_result)
    return self_result
