from knowledge.query import analyze


def test_definition_classification_and_topic():
    q = analyze("What is cognitive dissonance?")
    assert q.qtype == "definition"
    assert q.topic == "cognitive dissonance"
    assert q.keywords == ["cognitive", "dissonance"]
    assert not q.is_programming


def test_howto_programming_detection():
    q = analyze("How do Python decorators work?")
    assert q.qtype == "howto"
    assert q.is_programming
    assert "python" in q.keywords
    assert "decorators" in q.keywords


def test_code_pattern_detection():
    q = analyze("Why does my_function() raise a TypeError?")
    assert q.is_programming


def test_history_question_is_not_programming():
    q = analyze("What caused the fall of the Roman Empire?")
    assert not q.is_programming
    assert "roman" in q.keywords
    assert "empire" in q.keywords


def test_person_question():
    q = analyze("Who was Carl Jung?")
    assert q.qtype == "person"
    assert q.topic == "carl jung"
