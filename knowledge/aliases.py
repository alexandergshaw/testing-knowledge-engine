"""Search aliases for concepts whose common name isn't how sources title their
content. Each entry is cheap and high-leverage: one alias list lets retrieval
find real, citable content for a whole family, instead of authoring a unit per
concept. Used by the multi-variant retrieval in pipeline.retrieve — tried only
when the direct query gaps, so aliases never override a good direct hit.

Hand-curated *vocabulary* (not content): naming the field's synonyms, the way a
reference librarian would. No LLM.
"""

ALIASES = {
    # The accumulator idiom: sources title it "Accumulator factory" (Rosetta /
    # Paul Graham) or discuss it as a running total / reduce.
    "accumulator pattern": ["accumulator factory", "running total", "reduce fold sum list"],
    "accumulator": ["accumulator factory", "running total"],
    # A few more programming idioms whose plain name rarely matches a title.
    "guard clause": ["guard clause early return", "guard statement programming"],
    "fence post error": ["off by one error"],
    "fizzbuzz": ["fizzbuzz", "fizz buzz"],
    "ragged array": ["jagged array"],
}


def aliases_for(text):
    """Alternative search phrases for any aliased concept named in `text`, or []."""
    lowered = text.lower()
    for key, alternatives in ALIASES.items():
        if key in lowered:
            return alternatives
    return []
