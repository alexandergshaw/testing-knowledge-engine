"""Curated, source-backed real-world case studies — one is placed on slide 3 of
every lecture deck (after the title + overview) to motivate the module.

Unlike an LLM, which can misdate or hallucinate events, every case study here is
hand-written from an established, well-documented incident and carries a real
Wikipedia citation (surfaced in the slide's speaker notes). Selection is
deterministic: the module's title + objectives are matched against domain
keywords; an unmatched module falls back to a general computer-science incident
so that — per the spec — every deck gets exactly one case study.

Preference, where a domain has options: a dramatic cautionary failure/breach
over an impressive build, because failures motivate fundamentals best. The last
bullet always ties the story to what students are about to learn.
"""

CASE_STUDIES = {
    "security": {
        "title": "Case Study: 2017 Equifax Breach",
        "bullets": [
            "In 2017, credit bureau Equifax exposed the personal data of about 147 million people.",
            "Attackers exploited a known web-server flaw that had gone unpatched for months.",
            "The fallout cost Equifax well over $1 billion and forced out its CEO.",
            "It shows why the security practices in this module matter from day one.",
        ],
        "source": {"title": "2017 Equifax data breach",
                   "url": "https://en.wikipedia.org/wiki/2017_Equifax_data_breach"},
    },
    "ml_ai": {
        "title": "Case Study: AlphaGo Defeats a Go Champion",
        "bullets": [
            "In 2016, DeepMind's AlphaGo beat world champion Lee Sedol at the ancient game of Go.",
            "Go has more board positions than there are atoms in the universe — long thought too complex for computers.",
            "AlphaGo learned winning strategies from data and self-play, not hand-coded rules.",
            "The same machine-learning ideas underpin what you'll explore in this module.",
        ],
        "source": {"title": "AlphaGo versus Lee Sedol",
                   "url": "https://en.wikipedia.org/wiki/AlphaGo_versus_Lee_Sedol"},
    },
    "os_concurrency": {
        "title": "Case Study: Therac-25 Radiation Overdoses",
        "bullets": [
            "Between 1985 and 1987, the Therac-25 medical machine delivered massive radiation overdoses.",
            "A race condition in its concurrent software let a dangerous mode slip through.",
            "At least six patients were seriously harmed before the cause was tracked down.",
            "It is the classic warning behind the careful systems thinking this module teaches.",
        ],
        "source": {"title": "Therac-25", "url": "https://en.wikipedia.org/wiki/Therac-25"},
    },
    "databases": {
        "title": "Case Study: 2017 GitLab Database Incident",
        "bullets": [
            "In 2017, a GitLab engineer accidentally deleted a live production database directory.",
            "All five of the company's backup methods were then found to have silently failed.",
            "The team livestreamed the recovery and still lost about six hours of user data.",
            "It is a vivid lesson in why the database design and backups in this module matter.",
        ],
        "source": {"title": "GitLab", "url": "https://en.wikipedia.org/wiki/GitLab"},
    },
    "web": {
        "title": "Case Study: Healthcare.gov Launch Failure",
        "bullets": [
            "In 2013, the U.S. Healthcare.gov site buckled under traffic almost immediately after launch.",
            "Only a handful of users could enroll on day one, despite a build costing hundreds of millions.",
            "Inadequate load testing and a tangled architecture were largely to blame.",
            "Solid web-development fundamentals — this module's focus — prevent failures like this.",
        ],
        "source": {"title": "HealthCare.gov", "url": "https://en.wikipedia.org/wiki/HealthCare.gov"},
    },
    "algorithms": {
        "title": "Case Study: 2010 Flash Crash",
        "bullets": [
            "On May 6, 2010, U.S. stock markets briefly lost nearly $1 trillion in value within minutes.",
            "Automated trading algorithms reacted to one another in a runaway feedback loop.",
            "Prices recovered most of the drop within the hour, but confidence was shaken.",
            "It shows how the algorithms you'll study can carry enormous real-world weight.",
        ],
        "source": {"title": "2010 flash crash", "url": "https://en.wikipedia.org/wiki/2010_flash_crash"},
    },
}

# General computer-science fallback for any module that matches no domain — still
# a specific, real, well-documented event (never fabricated).
DEFAULT = {
    "title": "Case Study: Mars Climate Orbiter",
    "bullets": [
        "In 1999, NASA lost the $327 million Mars Climate Orbiter just as it reached the planet.",
        "One software module worked in metric units while another used imperial — and nobody caught it.",
        "The tiny mismatch sent the craft too close to Mars, where it broke apart.",
        "It is a powerful reminder that small code details — the kind this module covers — really matter.",
    ],
    "source": {"title": "Mars Climate Orbiter",
               "url": "https://en.wikipedia.org/wiki/Mars_Climate_Orbiter"},
}

# Domain keywords, checked against the lowercased title + objectives. Order is the
# tie-break when two domains score equally (most specific / most dramatic first).
_MATCHERS = {
    "security": (
        "security", "cyber", "hacking", "hacker", "encryption", "cryptograph",
        "malware", "breach", "vulnerabilit", "penetration", "firewall", "phishing",
    ),
    "ml_ai": (
        "machine learning", "artificial intelligence", "deep learning",
        "neural network", "neural net", "reinforcement learning",
    ),
    "os_concurrency": (
        "operating system", "kernel", "concurren", "thread", "multithread",
        "deadlock", "race condition", "process scheduling", "mutex", "semaphore",
    ),
    "databases": (
        "database", "sql", "nosql", "relational", "data storage", "data modeling",
    ),
    "web": (
        "web development", "web design", "website", "frontend", "front-end",
        "backend", "back-end", "full stack", "full-stack", "html", "css",
        "react", "angular", "django", "flask",
    ),
    "algorithms": (
        "algorithm", "data structure", "sorting", "complexity", "big o",
        "dynamic programming",
    ),
}
_ORDER = ("security", "ml_ai", "os_concurrency", "databases", "web", "algorithms")


def case_study_for(title, objectives=""):
    """The best-matching curated case study for a module, or the general
    computer-science default. Always returns a case study (title, bullets,
    source) — there is no 'no match' outcome, matching the spec's rule that
    every deck carries exactly one."""
    text = f"{title} {objectives}".lower()
    best, best_score = None, 0
    for domain in _ORDER:
        score = sum(1 for keyword in _MATCHERS[domain] if keyword in text)
        if score > best_score:
            best, best_score = domain, score
    return CASE_STUDIES[best] if best else DEFAULT
