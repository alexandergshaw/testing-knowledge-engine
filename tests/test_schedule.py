from knowledge.schedule import (
    _filter_topics,
    _weave_mentions,
    allocate,
    analyze_description,
    extract_mentions,
)

DESCRIPTION = (
    "An introductory college course in Python programming. Students will learn "
    "the fundamentals of programming, covering variables, control flow, "
    "functions, data structures, file handling, and object-oriented programming."
)


def test_analyze_description_finds_subject():
    query = analyze_description(DESCRIPTION)
    assert query.subject == "Python"
    assert query.is_programming
    assert query.qtype == "list"


def test_analyze_description_non_programming():
    query = analyze_description(
        "A survey course in introductory psychology, exploring perception, "
        "memory, and human development."
    )
    assert query.subject == "Psychology"
    assert not query.is_programming


ETHICAL_HACKING = (
    "Ethical Hacking is a course designed to introduce students to the "
    "fundamentals of hacking and the ethics involved in hacking systems. "
    "Students will learn about malware, wireless security, cryptography, "
    "system architecture, and more to best understand system weaknesses in "
    "order to strengthen a company's defense against cyber attacks."
)


def test_subject_statement_beats_lexicon_hijack():
    # "ethics" is in the field lexicon, but the description names its subject.
    query = analyze_description(ETHICAL_HACKING)
    assert query.subject == "Ethical hacking"


def test_ethical_hacking_mentions():
    mentions = extract_mentions(ETHICAL_HACKING)
    assert "malware" in mentions
    assert "wireless security" in mentions
    assert "cryptography" in mentions
    assert "system architecture" in mentions
    assert "fundamentals of hacking" in mentions


CYBERSECURITY = (
    "A cybersecurity course. Topics include cybersecurity policy, "
    "cybersecurity law, cybersecurity research, cyber operations, ethical "
    "hacking, protocols, cyber architecture, security architecture, digital "
    "forensics, intrusion detection, malware, cloud computing, and computer "
    "networking. This course will also offer hands-on practical and virtual labs."
)


def test_noun_phrase_subject_before_course():
    query = analyze_description(CYBERSECURITY)
    assert query.subject == "Computer security"


def test_topics_include_mentions():
    mentions = extract_mentions(CYBERSECURITY)
    assert "cybersecurity policy" in mentions
    assert "ethical hacking" in mentions
    assert "digital forensics" in mentions
    assert "computer networking" in mentions
    assert len(mentions) >= 12


OOP = (
    "This course is Object Oriented Programming. This course is for students "
    "who want to learn how to write computer programs. Topics covered include "
    "control structures, simple data types, arrays, strings, structures, data "
    "files, objects, classes, and debugging techniques."
)


def test_course_is_subject_pattern():
    query = analyze_description(OOP)
    assert query.subject == "Object-oriented programming"
    assert query.is_programming


def test_course_is_for_students_does_not_capture():
    query = analyze_description(
        "This course is for students who want to learn carpentry skills, "
        "covering joinery, framing, and finishing."
    )
    # "for students..." must not be mistaken for a subject.
    assert query.subject != "For students"


def test_extract_mentions_pulls_required_topics():
    mentions = extract_mentions(DESCRIPTION)
    assert "variables" in mentions
    assert "control flow" in mentions
    assert "object-oriented programming" in mentions
    # "the fundamentals of programming" leads with a trimmed qualifier
    assert all(len(m.split()) <= 6 for m in mentions)


def test_weave_mentions_inserts_missing_topics_in_order():
    topics = [
        {"name": "Variables", "citations": [1], "position": 0.1},
        {"name": "Classes", "citations": [1], "position": 0.9},
    ]
    out = _weave_mentions(topics, ["variables", "control flow", "classes"])
    names = [t["name"] for t in out]
    assert names.count("Variables") == 1           # matched, not duplicated
    assert "Control flow" in names                  # missing one woven in
    # description order ≈ teaching order: control flow lands between them
    assert names.index("Variables") < names.index("Control flow") < names.index("Classes")


def test_filter_topics_drops_uncorroborated_link_farm_items():
    citations = [
        {"title": "Python Programming", "url": "u1", "source": "Wikiversity"},
        {"title": "Outline of Python", "url": "u2", "source": "Wikipedia"},
    ]
    topics = [
        {"name": "Variables", "citations": [1, 2], "position": 0.1},
        {"name": "Loops", "citations": [1], "position": 0.2},      # curated page
        {"name": "Functions", "citations": [1], "position": 0.3},
        {"name": "Classes", "citations": [1, 2], "position": 0.6},
        {"name": "YouTube", "citations": [2], "position": 0.8},    # outline only
    ]
    kept = [t["name"] for t in _filter_topics(topics, citations, [])]
    assert "Variables" in kept
    assert "Loops" in kept
    assert "YouTube" not in kept


def test_filter_topics_falls_back_when_too_sparse():
    citations = [{"title": "Outline of X", "url": "u", "source": "Wikipedia"}]
    topics = [
        {"name": f"T{i}", "citations": [1], "position": i / 5} for i in range(5)
    ]
    # Nothing passes the strict filter, so the unfiltered list comes back.
    assert len(_filter_topics(topics, citations, [])) == 5


def test_allocate_more_topics_than_weeks_groups_contiguously():
    weeks = allocate([f"T{i}" for i in range(10)], 4)
    assert len(weeks) == 4
    assert [w["week"] for w in weeks] == [1, 2, 3, 4]
    flattened = [t for w in weeks for t in w["topics"]]
    assert flattened == [f"T{i}" for i in range(10)]  # order preserved


def test_allocate_fewer_topics_than_weeks_spans_and_reviews():
    weeks = allocate(["Intro", "Loops", "Functions"], 6)
    assert len(weeks) == 6
    flattened = [t for w in weeks for t in w["topics"]]
    assert "Review and final assessment" in flattened[-1]
    assert any("(continued)" in t for t in flattened)
    assert flattened.index("Intro") < flattened.index("Loops") < flattened.index("Functions")


def test_allocate_long_term_gets_midterm_review():
    weeks = allocate([f"T{i}" for i in range(8)], 14)
    flattened = [t for w in weeks for t in w["topics"]]
    assert len(weeks) == 14
    assert "Midterm review and practice" in flattened
    assert flattened[-1] == "Review and final assessment"


def test_alphabetical_catalog_detection():
    from knowledge.schedule import _is_alphabetical, _sample_evenly

    branches = ["Abnormal", "Applied", "Asian", "Behavioral", "Biological",
                "Clinical", "Cognitive", "Cultural", "Developmental"]
    lessons = ["Introduction", "Variables", "Conditions", "Loops",
               "Functions", "Strings", "Lists", "Dictionaries", "Classes"]
    assert _is_alphabetical(branches)
    assert not _is_alphabetical(lessons)
    sampled = _sample_evenly(list(range(100)), 10)
    assert len(sampled) == 10
    assert sampled[0] == 0 and sampled[-1] == 90


def test_allocate_exact_fit():
    weeks = allocate(["A", "B", "C"], 3)
    assert [w["topics"] for w in weeks] == [["A"], ["B"], ["C"]]
