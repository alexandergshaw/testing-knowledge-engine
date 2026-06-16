"""Concepts the retrieval-quality benchmark scores (see test_retrieval_quality.py
and scripts/record_retrieval_fixtures.py).

Each case is judged on whether the engine's retrieval is *acceptable*: either it
cites a topically-relevant article (a title containing one of `keywords`) or it
honestly returns nothing (a gap). The failure we're hunting is "confidently
wrong" — citing an off-topic article (e.g. accumulator pattern -> Hough
transform) with non-none confidence.

`xfail` marks a case the engine gets wrong at the D-a baseline; D-b's relevance
gate is expected to flip it.
"""

CASES = [
    # The motivating failure: "accumulator" only appears in off-topic articles
    # (Hough transform); the D-b relevance gate turns this into an honest gap.
    {"objective": "Use the accumulator pattern to process data", "keywords": ["accumulator"]},
    # Clear, well-matched topics — retrieval should already nail these.
    {"objective": "Explain photosynthesis", "keywords": ["photosynthesis"]},
    {"objective": "Describe natural selection", "keywords": ["natural selection", "evolution"]},
    {"objective": "Explain supply and demand", "keywords": ["supply", "demand"]},
    {"objective": "Explain cognitive dissonance", "keywords": ["dissonance"]},
    {"objective": "Describe Newton's laws of motion", "keywords": ["newton"]},
    {"objective": "Explain recursion", "keywords": ["recursion", "recursive"]},
    {"objective": "Describe the water cycle", "keywords": ["water cycle", "hydrolog"]},
    {"objective": "Calculate the standard deviation of a data set",
     "keywords": ["standard deviation", "deviation"]},
    {"objective": "Explain mitosis", "keywords": ["mitosis"]},
    {"objective": "Define opportunity cost", "keywords": ["opportunity"]},
    {"objective": "Summarize the causes of the French Revolution",
     "keywords": ["french revolution", "revolution"]},
]

# Gap corpus: programming idioms/tasks that general encyclopedias don't title an
# article for, so they baseline as honest gaps. These demand *relevant* content
# (a gap is not good enough) and start xfail; closing them — via Q&A
# content-relevance (R-a), Rosetta Code/Wikibooks (R-b), aliases (R-c) — flips
# them to pass. This is the gap-closure score the research loop drives up.
GAP_CORPUS = [
    # Closed by R-c: the alias map routes "accumulator pattern" to Rosetta's
    # "Accumulator factory" / Stack Overflow's "running total" content.
    {"objective": "Use the accumulator pattern to process data", "domain": "programming",
     "keywords": ["accumulator", "sum", "total", "reduce", "fold"], "require_relevant": True},
    # Closed by R-a (Q&A content-relevance) — now strict regression guards.
    {"objective": "Keep a running total in a loop", "domain": "programming",
     "keywords": ["running total", "accumulator", "sum", "loop"], "require_relevant": True},
    {"objective": "Swap two variables in place", "domain": "programming",
     "keywords": ["swap"], "require_relevant": True},
    {"objective": "Reverse a string", "domain": "programming",
     "keywords": ["reverse", "string"], "require_relevant": True},
    {"objective": "Read a file line by line", "domain": "programming",
     "keywords": ["file", "read", "line"], "require_relevant": True},
]

ALL_CASES = CASES + GAP_CORPUS

