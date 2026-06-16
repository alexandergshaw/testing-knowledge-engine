from knowledge import quant_library


def test_match_recognizes_quant_concepts():
    assert quant_library.match("Solve quadratic equations") == "Quadratic Equations"
    assert quant_library.match("Apply the Pythagorean theorem") == "Pythagorean Theorem"
    assert quant_library.match("Differentiate polynomial functions") == "Derivatives"
    assert quant_library.match("Use Ohm's law to find voltage") == "Ohm's Law"
    assert quant_library.match("Calculate the mean of a data set") == "Arithmetic Mean"
    # Non-quantitative objectives match nothing -> conceptual fallback.
    assert quant_library.match("Explain photosynthesis") is None


def test_every_unit_is_well_formed_and_distinct():
    for name in quant_library.LIBRARY:
        unit = quant_library.unit_for(name)
        assert unit is not None, name
        assert unit["worked_example"]["problem"] and unit["worked_example"]["steps"]
        assert unit["practice"]["problem"]
        assert unit["answer"]["steps"]
        # The practice problem and the worked example are different problems,
        # so their solution steps must differ (the answer is genuinely distinct).
        assert unit["answer"]["steps"] != unit["worked_example"]["steps"], name
        assert quant_library.explanation_for(name)


def test_unit_for_missing_returns_none():
    assert quant_library.unit_for("Nonexistent Concept") is None


def test_find_all_mines_multiple_concepts():
    found = quant_library.find_all("Homework: solve quadratic equations and use Ohm's law.")
    assert "Quadratic Equations" in found and "Ohm's Law" in found
    assert quant_library.find_all("Write an essay about history") == []
