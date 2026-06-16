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
    content_tokens,
    tokenize,
)
from .ranking import rank, split_sentences
from .slides import (
    add_bullet_slide,
    add_code_box,
    add_code_example_slide,
    add_content_slide,
    add_list_slide,
    add_practice_slide,
    add_problem_slide,
    add_text_box,
    add_title_slide,
    add_walkthrough_slide,
    clean_title,
    deck_bytes,
    new_deck,
    set_notes,
)
from .synthesize import FALLBACK_ANSWER, sanitize_layman, synthesize
from . import case_study, concept_library, quant_library

log = logging.getLogger(__name__)

MAX_OBJECTIVES = 20
MAX_POINTS_PER_SLIDE = 6
MAX_EXAMPLES_PER_OBJECTIVE = 2
MAX_CONCEPT_SLIDES = 15
MAX_CODE_LINES = 14
MAX_HOMEWORK_PREREQS = 6     # extra prerequisite-coverage sections a homework can add
HOMEWORK_OVERLAP_FLOOR = 0.85  # drop only a retrieved example that nearly duplicates the homework
                               # (concept-level overlap is expected and fine)
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


# Lines that are code or raw fragments, not learning objectives — kept out of
# decks (conservative: real objectives never contain these patterns).
_NOISE_OBJECTIVE = re.compile(r"==|!=|->|::|[{}\[\]]|[a-zA-Z_]\w*\s*=\s*\S|^\s*\(")


def _is_noise_objective(text):
    return len(text) > 160 or bool(_NOISE_OBJECTIVE.search(text))


def _finalize(items, limit):
    seen, out = set(), []
    for item in items:
        objective = re.sub(
            r"^(?:be\s+able\s+to|able\s+to|to)\s+", "", item.strip(" .;:-*•–"), flags=re.IGNORECASE
        )
        objective = re.sub(r"\s+", " ", objective).strip()
        key = objective.lower()
        if not objective or key in seen or _is_noise_objective(objective):
            continue
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
    quant_units: list = field(default_factory=list)       # worked-problem units (quantitative lectures)
    questions: list = field(default_factory=list)         # review questions (conceptual lectures)
    citations: list = field(default_factory=list)
    confidence: str = "none"
    provenance: str = "none"                              # curated | synthesized | gap
    prerequisite: bool = False                            # homework-driven coverage (kept off the agenda)


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
    blocks = _code_blocks(passages, ranked, limit=1)
    return blocks[0] if blocks else (None, None)


def _code_blocks(passages, ranked, limit=2):
    """Up to `limit` *distinct* usable code blocks (deduped by content), preferring
    passages backing the top-ranked sentences. Returns [(lines, passage), ...].
    A second distinct block lets a retrieved unit show a genuinely different
    answer from its example."""
    ordered, seen = [], set()
    for passage in [s.passage for s in ranked] + list(passages):
        if id(passage) not in seen:
            seen.add(id(passage))
            ordered.append(passage)
    blocks, contents = [], set()
    for passage in ordered:
        for block in passage.code or []:
            lines = _code_lines(block)
            key = "\n".join(lines)
            if lines and key not in contents:
                contents.add(key)
                blocks.append((lines, passage))
                if len(blocks) >= limit:
                    return blocks
    return blocks


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
        blocks = _code_blocks(passages, ranked, limit=2)
        if blocks:
            lines, passage = blocks[0]
            result = {
                "kind": "code",
                "concept": concept,
                "text": sanitize_layman(_best_example_text(ranked)) or f"A worked {concept.lower()} example.",
                "lines": lines,
                # a distinct second snippet for a genuinely different answer, if found
                "answer_lines": blocks[1][0] if len(blocks) > 1 else None,
                "language": language,
                "title": passage.title,
                "url": passage.url,
                "source": passage.source,
            }
    except Exception:
        log.warning("concept code fetch failed: %s", concept, exc_info=True)
    _concept_cache.set(key, (result,))  # cache misses too, to avoid re-fetching
    return result


# Deterministic, no-LLM descriptions of common code-line shapes — used to build
# a walkthrough for an *uncurated* concept whose code was retrieved from the web.
_ASSIGN = re.compile(r"^([A-Za-z_][\w\.\[\]]*)\s*=\s*[^=]")


def _describe_line(line):
    """A plain-English description of one line of code, or None to skip it."""
    text = line.strip()
    if not text:
        return None
    if text.startswith("#"):
        return f"Comment: {text.lstrip('# ').strip()}".rstrip()
    if text.startswith(("def ", "async def ")):
        name = re.sub(r"^(?:async\s+)?def\s+(\w+).*", r"\1", text)
        return f"Defines the function {name}."
    if text.startswith("class "):
        name = re.sub(r"^class\s+(\w+).*", r"\1", text)
        return f"Defines the class {name}."
    if text.startswith(("for ", "while ")):
        return "Starts a loop that repeats the indented block."
    if text.startswith(("if ", "elif ")) or text == "else:":
        return "Branches based on a condition."
    if text.startswith("return"):
        return "Returns a value to the caller."
    if text.startswith(("import ", "from ")):
        return "Imports code from another module."
    if re.match(r"\w+\s*\(", text) and "print(" in text:
        return "Prints output to the screen."
    match = _ASSIGN.match(text)
    if match:
        return f"Assigns a value to {match.group(1)}."
    return f"Runs: {text}"


def _describe_code(lines):
    """A best-effort line-by-line walkthrough of a retrieved code block."""
    described = [d for d in (_describe_line(line) for line in lines) if d]
    return described or ["Read each line and predict what it does before running it."]


def _concept_unit(concept, language):
    """The full Example/Walkthrough/Practice/Answer unit for one concept, or
    None. Curated content first (instant, distinct answer); otherwise a
    deterministic unit built around retrieved example code — the practice slide
    reuses the example as a read-only reference, and (with no LLM to author a
    fresh solution) the answer reuses it as the worked solution."""
    curated = concept_library.unit_for(concept, language)
    if curated:
        return {"concept": concept, **curated, "title": "", "url": "", "source": "Curated"}

    fetched = _concept_code(concept, language)
    if not fetched:
        return None
    lines = fetched["lines"]
    # Prefer a distinct second snippet as the answer; fall back to the example
    # (an honest "here's the worked version" when only one snippet was found).
    answer_lines = fetched.get("answer_lines")
    if answer_lines:
        answer = {"caption": "An alternative, runnable solution.", "lines": list(answer_lines)}
    else:
        answer = {"caption": "A correct, runnable version of the example.", "lines": list(lines)}
    return {
        "concept": concept,
        "language": fetched.get("language", language),
        "example": {"caption": fetched.get("text", ""), "lines": lines},
        "walkthrough": _describe_code(lines),
        "practice": [
            f"Recreate this {concept.lower()} example yourself, from scratch.",
            "Run it and confirm you get the same result.",
        ],
        "answer": answer,
        "title": fetched.get("title", ""),
        "url": fetched.get("url", ""),
        "source": fetched.get("source", ""),
    }


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
    query, passages, ranked, programming_lecture=False, limit=MAX_EXAMPLES_PER_OBJECTIVE,
    homework_tokens=None,
):
    """Worked examples for an objective.

    Programming lecture: examples are driven per-concept elsewhere (see
    `_attach_concept_examples`), so this returns []. Otherwise: code (if any) +
    'for example…' prose + a best-effort fallback sentence. When `homework_tokens`
    are given, any example whose wording mostly echoes the homework is dropped so
    the deck never restates an assignment question."""
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
    examples = examples[:limit]
    if homework_tokens:
        examples = [e for e in examples if not _overlaps_homework(e.get("text", ""), homework_tokens)]
    return examples


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


# Field/keyword markers for quantitative (problem-solving) subjects.
_QUANT_TERMS = frozenset(
    """math mathematics maths algebra calculus geometry trigonometry arithmetic
    precalculus statistics statistical probability physics mechanics kinematics
    chemistry quantitative equations equation""".split()
)


def _is_quantitative(objectives, title=""):
    """A quantitative lecture: the subject is math/physics/chemistry/statistics,
    or at least one objective names a curated worked-problem concept."""
    words = set(tokenize(title)) | set(tokenize(" ".join(objectives)))
    if words & _QUANT_TERMS:
        return True
    return any(quant_library.match(objective) for objective in objectives)


def classify_subject(objectives, title=""):
    """The lecture profile that drives the deck's structure: 'programming'
    (per-concept code units), 'quantitative' (worked-problem units), or
    'conceptual' (illustration + review questions). Deterministic — no model,
    no network."""
    if is_programming_lecture(objectives, title):
        return "programming"
    if _is_quantitative(objectives, title):
        return "quantitative"
    return "conceptual"


def _curated_explanation(objective):
    """Hand-written layman bullets for a concept or topic, or None. Checks
    programming concepts, then quantitative concepts, then conceptual topics."""
    for concept in extract_concepts(analyze(objective)):
        bullets = concept_library.explanation_for(concept)
        if bullets:
            return bullets
    qname = quant_library.match(objective)
    if qname:
        bullets = quant_library.explanation_for(qname)
        if bullets:
            return bullets
    topic = concept_library.match_topic(objective)
    return concept_library.explanation_for(topic) if topic else None


def _curated_illustration(objective):
    """A curated real-world illustration sentence for a conceptual objective, or
    None (programming/quantitative concepts use code/worked examples instead)."""
    topic = concept_library.match_topic(objective)
    return concept_library.illustration_for(topic) if topic else None


def _build_objective(objective, context="", homework_tokens=None, domain=None):
    # Prefer curated, Gemini-quality layman content — no network, no jargon.
    curated = _curated_explanation(objective)
    if curated is not None:
        illustration = _curated_illustration(objective)
        examples = (
            [{"kind": "prose", "text": illustration, "title": "", "url": "", "source": "Curated"}]
            if illustration
            else []
        )
        return ObjectiveResult(
            objective=objective, points=curated, examples=examples, citations=[],
            confidence="high", provenance="curated",
        )

    # Fallback: retrieve, synthesize, and strip encyclopedic markup. Examples are
    # always extracted (an illustration backs the conceptual unit when this
    # objective gets no richer code/worked unit); render precedence avoids dupes.
    query = analyze(objective)
    # Domain anchoring: bias the keyword search toward the module's field so an
    # ambiguous objective ("accumulator pattern") retrieves the right sense.
    if domain == "programming" and "programming" not in query.search_terms:
        query.search_terms = f"{query.search_terms} programming".strip()
    if context:
        query.search_terms = f"{query.search_terms} {context}".strip()
    passages = fetch(query, select_sources(query, domain))
    if not passages:
        return ObjectiveResult(objective, provenance="gap")
    ranked = rank(query, passages)
    synth = synthesize(query, ranked)
    points = [p for p in (sanitize_layman(point) for point in _to_points(synth["answer"])) if p]
    return ObjectiveResult(
        objective=objective,
        points=points,
        examples=extract_examples(query, passages, ranked, homework_tokens=homework_tokens),
        citations=synth["citations"],
        confidence=synth["confidence"],
        provenance="synthesized" if points else "gap",
    )


def _safe_build(objective, context="", homework_tokens=None, domain=None):
    try:
        return _build_objective(objective, context, homework_tokens, domain)
    except Exception:
        log.warning("objective failed: %s", objective, exc_info=True)
        return ObjectiveResult(objective)


# --- deck assembly -----------------------------------------------------------


def _short(text):
    text = text.strip()
    if len(text) <= TITLE_SHORT_LIMIT:
        return text
    return text[: TITLE_SHORT_LIMIT - 1].rstrip() + "…"


_TITLE_FILLER = re.compile(r"^(?:appropriate|examples of|how to|the|a|an)\s+", re.IGNORECASE)


def _topic_title(objective):
    """A clean topic title from an objective: drop the leading action verb and a
    little filler ('Choose appropriate numeric data types' -> 'Numeric Data
    Types', 'Provide examples of Computer Science...' -> 'Computer Science...')."""
    text = objective.strip()
    match = re.match(r"^(\w+)\s+(.*)$", text)
    if match and match.group(1).lower() in BLOOM_VERBS:
        text = match.group(2)
    text = _TITLE_FILLER.sub("", text)
    return text.strip() or objective


def _ref_key(item):
    return (item.get("title", ""), item.get("url", ""), item.get("source", ""))


# Honest, consistent provenance line for a slide's speaker notes.
_PROVENANCE_NOTE = {
    "curated": "Provenance: curated content (engine-authored, high confidence).",
    "synthesized": "Provenance: synthesized from public sources — verify before teaching.",
    "gap": "Provenance: gap — no reliable source found. Needs review / your own material.",
}


def _provenance_line(result):
    note = _PROVENANCE_NOTE.get(result.provenance)
    if not note:
        return ""
    if result.provenance == "synthesized":
        note += f" (confidence: {result.confidence})"
    return note


def _explanation_notes(index, result):
    lines = [f"Objective {index}: {result.objective}", ""]
    provenance = _provenance_line(result)
    if provenance:
        lines.append(provenance)
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


def _unit_source(unit):
    """The 'Source:' line for a concept unit's speaker notes."""
    if not unit.get("url"):
        return "Source: Curated lecture content."
    return f"Source: {unit.get('title', '')} ({unit.get('source', '')}) — {unit['url']}"


def _add_concept_unit(deck, unit, footer, register):
    """Render one coding concept as the fixed Example -> Walkthrough -> Practice
    -> Answer unit. The example's code is the single reference snippet the
    walkthrough and practice slides reuse (by construction, so a generated
    practice snippet can never leak the answer); only the answer slide carries
    its own distinct, runnable solution."""
    concept = unit["concept"]
    language = unit.get("language", "")
    example = unit["example"]
    ref_lines = example["lines"]
    source = _unit_source(unit)

    example_slide = add_code_example_slide(
        deck,
        f"Example: {concept}",
        example.get("caption") or f"A worked {concept.lower()} example.",
        language,
        ref_lines,
    )
    set_notes(example_slide, f"Talking points:\nIntroduce the example, then read the code aloud.\n{source}")

    walkthrough_slide = add_walkthrough_slide(
        deck, f"Walkthrough: {concept}", language, ref_lines, unit["walkthrough"]
    )
    set_notes(
        walkthrough_slide,
        f"Talking points:\nExplain the code line by line, tying each line back to the concept.\n{source}",
    )

    practice_slide = add_practice_slide(
        deck, f"Practice: {concept}", language, ref_lines, unit["practice"]
    )
    set_notes(
        practice_slide,
        "Talking points:\nGive students time to attempt the challenge. The code shown is the "
        "worked example for reference only — it is not the solution.",
    )

    answer = unit["answer"]
    answer_slide = add_code_example_slide(
        deck,
        f"Answer: {concept}",
        answer.get("caption") or "A correct solution.",
        language,
        answer["lines"],
    )
    set_notes(
        answer_slide,
        "Talking points:\nReveal after students attempt the challenge, then compare it with their work.",
    )

    register(unit)


def _add_conceptual_unit(deck, result, footer, register):
    """The non-programming rhythm after a concept slide: an Illustration (a
    retrieved real-world example, when one was found) followed by a Check Your
    Understanding slide whose review questions carry model talking points in the
    speaker notes. No code."""
    topic = _topic_title(result.objective)

    example = result.examples[0] if result.examples else None
    if example:
        slide = add_content_slide(deck, f"Illustration: {topic}", footer=footer)
        if example.get("kind") == "code" and example.get("lines"):
            add_text_box(slide, example.get("text") or "Worked example:", top=1.7, height=1.3, size=18)
            add_code_box(slide, example["lines"], top=3.5)
        else:
            add_text_box(slide, example["text"], top=1.7, height=4.5, size=18)
        set_notes(slide, _example_notes(example))
        register(example)

    if result.questions:
        notes = ["Suggested talking points (model answers):"]
        notes.extend(f"- {point}" for point in (result.points or []))
        if result.citations:
            notes.append(
                "Sources: " + "; ".join(f"{c['title']} ({c['source']})" for c in result.citations)
            )
        add_bullet_slide(
            deck,
            f"Check Your Understanding: {topic}",
            result.questions,
            notes="\n".join(notes),
            footer=footer,
        )


def _add_quant_unit(deck, unit, footer):
    """Render one quantitative concept as Worked Example -> Practice -> Answer.
    The Worked Example shows the full method; Practice shows only the problem
    (no solution); Answer carries the distinct solution to the practice problem."""
    concept = unit["concept"]
    worked = unit["worked_example"]
    practice = unit["practice"]
    answer = unit["answer"]

    worked_slide = add_problem_slide(
        deck, f"Worked Example: {concept}", worked["problem"], worked["steps"], footer=footer
    )
    set_notes(worked_slide, "Talking points:\nWork through each step aloud, explaining the reasoning.")

    practice_slide = add_problem_slide(
        deck,
        f"Practice: {concept}",
        practice["problem"],
        ["Work it out on your own, then check the Answer slide."],
        footer=footer,
    )
    set_notes(practice_slide, "Talking points:\nGive students time to attempt the problem before revealing the answer.")

    answer_slide = add_problem_slide(
        deck, f"Answer: {concept}", practice["problem"], answer["steps"], footer=footer
    )
    set_notes(answer_slide, "Talking points:\nReveal after the attempt; have students compare their steps.")


def _add_case_study(deck, title, results, footer):
    """Add the single, deterministically chosen real-world case-study slide. No
    code; the real source is cited in the speaker notes so the claim is checkable
    (we never fabricate an event — curated facts only)."""
    case = case_study.case_study_for(title, " ".join(result.objective for result in results))
    source = case.get("source")
    notes = ["Talking points:", "Open with this real-world story to motivate the module."]
    if source:
        notes.append(f"Source: {source['title']} — {source['url']}")
    notes.append("Stick to the established facts; do not embellish.")
    add_bullet_slide(deck, case["title"], case["bullets"], notes="\n".join(notes), footer=footer)


def _add_prereq_divider(deck, footer):
    """A section header before homework-driven prerequisite coverage."""
    add_bullet_slide(
        deck,
        "Prerequisite Skills for the Assignment",
        [
            "These aren't new objectives — they're the building blocks you'll need "
            "to complete the assignment confidently.",
        ],
        notes=(
            "These sections were added to cover what the assignment requires. The "
            "assignment's own questions and answers are deliberately not shown."
        ),
        footer=footer,
    )


def _prereq_notes(result):
    lines = [
        "Prerequisite skill for the assignment — taught so students can complete "
        "the homework on their own (the assignment itself is never shown)."
    ]
    if result.citations:
        lines.append(
            "Sources: " + "; ".join(f"{c['title']} ({c['source']})" for c in result.citations)
        )
    return "\n".join(lines)


def build_module_deck(title, results, source_label=None):
    deck = new_deck()
    footer = title or "Module Lecture"
    # Prerequisite (homework-driven) sections are taught but kept off the agenda.
    agenda = [result for result in results if not result.prerequisite]
    subtitle = f"{len(agenda)} learning objectives"
    if source_label:
        subtitle += f" · from {source_label}"
    add_title_slide(deck, title or "Module Lecture", subtitle)

    # Module overview (agenda) — clean topic titles, compact list slide.
    add_list_slide(
        deck,
        "Module Overview",
        [f"{i}. {clean_title(_topic_title(result.objective))}" for i, result in enumerate(agenda, 1)],
        footer=footer,
    )

    # A real-world case study to motivate the module — deterministic, curated,
    # and cited (slide 3, before any concept slides).
    _add_case_study(deck, title, results, footer)

    refs, ref_order = {}, []

    def register(item):
        # Only retrieved sources (with a URL) become references — curated content
        # isn't cited.
        key = _ref_key(item)
        if item.get("url") and key not in refs:
            refs[key] = len(refs) + 1
            ref_order.append(item)

    objective_index = 0
    divider_added = False
    for result in results:
        if result.prerequisite and not divider_added:
            _add_prereq_divider(deck, footer)
            divider_added = True
        points = result.points or [
            "No reliable source was found for this objective — try rephrasing it "
            "or supplement from your own materials."
        ]
        if result.prerequisite:
            notes = _prereq_notes(result)
        else:
            objective_index += 1
            notes = _explanation_notes(objective_index, result)
        add_bullet_slide(
            deck,
            _topic_title(result.objective),
            points,
            notes=notes,
            footer=footer,
        )
        for citation in result.citations:
            register(citation)

        if result.concept_examples:
            # Programming: each coding concept gets a fixed 4-slide unit
            # (Example -> Walkthrough -> Practice -> Answer).
            for unit in result.concept_examples:
                _add_concept_unit(deck, unit, footer, register)
        elif result.quant_units:
            # Quantitative: Worked Example -> Practice -> Answer.
            for unit in result.quant_units:
                _add_quant_unit(deck, unit, footer)
        elif result.questions:
            # Conceptual (non-programming): Illustration + Check Your Understanding.
            _add_conceptual_unit(deck, result, footer, register)
        else:
            # Generic fallback: prose (or code) example slides.
            for example in result.examples:
                example_slide = add_content_slide(
                    deck, f"Example — {_short(result.objective)}", footer=footer
                )
                if example["kind"] == "code":
                    add_text_box(example_slide, example.get("text") or "Worked example:", top=1.7, height=1.3, size=18)
                    add_code_box(example_slide, example["lines"], top=3.5)
                else:
                    add_text_box(example_slide, example["text"], top=1.7, height=4.5, size=18)
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
    """Give each programming concept the lecture covers its own worked-example
    unit (Example/Walkthrough/Practice/Answer), attached to the first objective
    that introduces it (de-duplicated). Units are built concurrently."""
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
        units = list(executor.map(lambda c: _concept_unit(c, language), order))
    for concept, unit in zip(order, units):
        if unit:
            owner[concept].concept_examples.append(unit)


# Objective verbs that change the kind of practice question worth asking.
_ACTION_VERBS = frozenset(
    """apply use implement write build create develop construct solve design
    calculate compute produce perform configure deploy model derive""".split()
)
_COMPARE_VERBS = frozenset("compare differentiate distinguish contrast relate".split())
_ANALYZE_VERBS = frozenset("analyze analyse evaluate assess critique interpret examine".split())


def _objective_verb(objective):
    match = re.match(r"\s*([a-zA-Z]+)", objective or "")
    verb = match.group(1).lower() if match else ""
    return verb if verb in BLOOM_VERBS else ""


def _review_questions(topic, objective="", next_topic=None):
    """Deterministic study questions for a topic, tuned to the objective's Bloom
    verb (recall vs apply vs compare vs analyze). No LLM: the instructor answers
    them from the cited explanation in the slide's notes."""
    topic = topic.strip().rstrip(".")
    verb = _objective_verb(objective)
    questions = [f"Define {topic} in your own words."]
    if verb in _ACTION_VERBS:
        questions += [
            f"Outline the steps to {verb} {topic}.",
            f"What is a common mistake to avoid when working with {topic}?",
        ]
    elif verb in _COMPARE_VERBS:
        questions += [
            f"Compare {topic} with a related approach.",
            f"When would you choose {topic}?",
        ]
    elif verb in _ANALYZE_VERBS:
        questions += [
            f"Evaluate when {topic} is the right choice.",
            f"What are the trade-offs of {topic}?",
        ]
    else:
        questions += [
            f"Explain why {topic} is important.",
            f"Describe a real-world example of {topic}.",
        ]
    if next_topic:
        nxt = next_topic.strip().rstrip(".")
        if nxt and nxt.lower() != topic.lower():
            questions.append(f"How does {topic} relate to {nxt}?")
    return questions


def _attach_review_questions(results):
    """The universal baseline: give each objective a short set of review
    questions, tuned to its verb and relating each to the next objective's topic."""
    topics = [_topic_title(result.objective) for result in results]
    for index, result in enumerate(results):
        next_topic = topics[index + 1] if index + 1 < len(topics) else None
        result.questions = _review_questions(topics[index], result.objective, next_topic)


def _attach_quant_units(results):
    """Quantitative lectures: give each objective that names a curated concept a
    worked-problem unit. Objectives with no match get nothing here and fall back
    to the conceptual rhythm (illustration + review questions)."""
    for result in results:
        name = quant_library.match(result.objective)
        if not name:
            continue
        unit = quant_library.unit_for(name)
        if unit:
            result.quant_units.append({"concept": name, **unit})


# --- homework-driven prerequisite coverage ----------------------------------


def _overlaps_homework(text, homework_tokens):
    """True when a candidate example's wording mostly echoes the homework — used
    to keep retrieved examples from accidentally restating an assignment item."""
    tokens = set(content_tokens(text))
    if not tokens or not homework_tokens:
        return False
    return len(tokens & homework_tokens) / len(tokens) >= HOMEWORK_OVERLAP_FLOOR


def _covered_concepts(profile, objectives):
    """The concepts/topics the objectives already teach, per profile."""
    covered = set()
    for objective in objectives:
        if profile == "programming":
            covered.update(extract_concepts(analyze(objective)))
        elif profile == "quantitative":
            name = quant_library.match(objective)
            if name:
                covered.add(name)
        else:
            topic = concept_library.match_topic(objective)
            if topic:
                covered.add(topic)
    return covered


def _homework_prereqs(profile, homework_text, covered):
    """Concepts a homework exercises that the objectives don't already cover —
    the prerequisite skills the deck should add (capped, agenda-excluded)."""
    if profile == "programming":
        names = extract_concepts(analyze(homework_text))
    elif profile == "quantitative":
        names = quant_library.find_all(homework_text)
    else:
        names = concept_library.find_topics(homework_text)
    prereqs = []
    for name in names:
        if name not in covered and name not in prereqs:
            prereqs.append(name)
    return prereqs[:MAX_HOMEWORK_PREREQS]


def build_lecture_deck(
    objectives_text, title="Module Lecture", source_label=None, homework_text=None, context_extra=None
):
    """The /api/v1/lecture entry point: returns (pptx_bytes, summary).
    `source_label` (an uploaded file's name) is shown on the title slide.
    `homework_text` (an optional assignment) adds prerequisite-skill coverage —
    the concepts it requires are taught, but it is never restated, solved, or
    shown anywhere in the deck. `context_extra` (e.g. an uploaded file's outline)
    only biases retrieval toward the module's framing; it generates no slides."""
    objectives = parse_objectives(objectives_text)
    if not objectives:
        raise LectureError("No learning objectives found in the provided text.")

    title = (title or "Module Lecture").strip() or "Module Lecture"
    homework_text = (homework_text or "").strip() or None
    cache_key = (
        title.lower(),
        tuple(o.lower() for o in objectives),
        source_label or "",
        homework_text or "",
        (context_extra or "")[:200],
    )
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    # The profile drives the deck's structure: programming gets per-concept code
    # units; everything else (conceptual) gets illustrations + review questions.
    profile = classify_subject(objectives, title)
    programming_lecture = profile == "programming"
    homework_tokens = set(content_tokens(homework_text)) if homework_text else None

    # Homework adds prerequisite coverage: concepts the assignment needs that the
    # objectives don't already teach. These become extra sections (off the
    # agenda); the homework text itself is never rendered. If it yields no usable
    # concepts, the deck is exactly as it would be without homework.
    prereq_concepts = (
        _homework_prereqs(profile, homework_text, _covered_concepts(profile, objectives))
        if homework_text
        else []
    )
    prereq_objectives = [f"Understand {name}" for name in prereq_concepts]

    # An uploaded file (or other supplemental material) biases retrieval toward
    # the module's framing — bounded to a handful of salient terms so it nudges
    # rather than derails the keyword search.
    context = context_terms(title) if title != "Module Lecture" else ""
    if context_extra:
        extra_terms = list(dict.fromkeys(content_tokens(context_extra)))[:12]
        context = (context + " " + " ".join(extra_terms)).strip()

    # The deck profile routes retrieval to the right sources for every objective.
    domain = profile if profile in ("programming", "quantitative") else None
    with ThreadPoolExecutor(max_workers=min(len(objectives) + len(prereq_objectives), 8)) as executor:
        builder = lambda o: _safe_build(o, context, homework_tokens, domain)
        results = list(executor.map(builder, objectives))
        prereq_results = list(executor.map(builder, prereq_objectives))
    for result in prereq_results:
        result.prerequisite = True
    results = results + prereq_results

    # Rich units where the concept is recognized: code units (programming) or
    # worked-problem units (quantitative). extract_concepts/quant matching is a
    # fast-path recognizer here, not a gate.
    if profile == "programming":
        _attach_concept_examples(results, objectives + prereq_objectives, title)
    elif profile == "quantitative":
        _attach_quant_units(results)

    # Universal baseline: every objective with no rich unit gets the conceptual
    # treatment (illustration + review questions). No objective is ever a bare
    # slide — the deck is complete for any subject, curated or not.
    _attach_review_questions([r for r in results if not r.concept_examples and not r.quant_units])

    payload = build_module_deck(title, results, source_label=source_label)
    summary = _deck_model(title, profile, results, len(prereq_results), source_label)
    self_result = (payload, summary)
    _cache.set(cache_key, self_result)
    return self_result


def _unit_kind(result):
    if result.concept_examples:
        return "code"
    if result.quant_units:
        return "worked_problem"
    if result.questions:
        return "conceptual"
    return "none"


def _deck_model(title, profile, results, prerequisite_count, source_label=None):
    """A serializable, provenance-tagged view of the deck — the knowledge other
    apps consume (returned by `?format=json`). Doubles as the log/archive summary."""
    sections, provenance_summary, citations, citation_keys = [], {}, [], set()
    for result in results:
        provenance_summary[result.provenance] = provenance_summary.get(result.provenance, 0) + 1
        for citation in result.citations:
            key = (citation.get("title"), citation.get("url"))
            if citation.get("url") and key not in citation_keys:
                citation_keys.add(key)
                citations.append(citation)
        sections.append(
            {
                "objective": result.objective,
                "topic": clean_title(_topic_title(result.objective)),
                "prerequisite": result.prerequisite,
                "provenance": result.provenance,
                "confidence": result.confidence,
                "needsReview": result.provenance == "gap",
                "unit": _unit_kind(result),
                "points": result.points,
                "citations": result.citations,
            }
        )
    objective_count = len(sections) - prerequisite_count
    return {
        "title": title,
        "profile": profile,
        "sourceFile": source_label,
        "objectives": objective_count,        # count of agenda objectives (back-compat)
        "objectiveCount": objective_count,
        "prerequisites": prerequisite_count,
        "provenanceSummary": provenance_summary,
        "sections": sections,
        "citations": citations,
    }
