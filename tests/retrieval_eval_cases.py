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
