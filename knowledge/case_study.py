"""Curated, source-backed real-world case studies — one is placed on slide 3 of
every lecture deck (after the title + overview) to motivate the module.

Unlike an LLM, which can misdate or hallucinate events, every case study here is
hand-written from an established, well-documented incident and carries a real
Wikipedia citation (surfaced in the slide's speaker notes). Selection is
deterministic: the module's title + objectives are matched against domain
keywords; an unmatched module falls back to a STEM default (computing/engineering)
or an otherwise subject-neutral one, so that — per the spec — every deck gets
exactly one case study.

Preference, where a domain has options: a dramatic cautionary failure/breach
over an impressive build, because failures motivate fundamentals best. The last
bullet always ties the story to what students are about to learn.
"""

import re

from .query import _PROGRAMMING_TERMS

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
    # --- other academic fields ---------------------------------------------
    "psychology": {
        "title": "Case Study: Stanford Prison Experiment",
        "bullets": [
            "In 1971, a Stanford study assigned students to be 'guards' or 'prisoners' in a mock prison.",
            "The guards quickly turned abusive and the study was halted after six of a planned fourteen days.",
            "It became a touchstone for debates about authority, conformity, and research ethics.",
            "It frames the questions about human behavior this module explores.",
        ],
        "source": {"title": "Stanford prison experiment",
                   "url": "https://en.wikipedia.org/wiki/Stanford_prison_experiment"},
    },
    "biology": {
        "title": "Case Study: Thalidomide Tragedy",
        "bullets": [
            "From 1957, the drug thalidomide was sold to ease morning sickness in pregnant women.",
            "It caused severe birth defects in thousands of babies before being withdrawn around 1961.",
            "The disaster transformed drug testing and safety regulation worldwide.",
            "It grounds why the biology and physiology in this module matter for real lives.",
        ],
        "source": {"title": "Thalidomide scandal",
                   "url": "https://en.wikipedia.org/wiki/Thalidomide_scandal"},
    },
    "economics": {
        "title": "Case Study: 2008 Financial Crisis",
        "bullets": [
            "In 2008, the collapse of a U.S. housing bubble triggered a global financial crisis.",
            "Major banks failed, markets crashed, and millions lost homes and jobs.",
            "Risky mortgage lending and opaque financial products were central causes.",
            "It shows why the economic principles in this module carry real-world stakes.",
        ],
        "source": {"title": "2007–2008 financial crisis",
                   "url": "https://en.wikipedia.org/wiki/2007%E2%80%932008_financial_crisis"},
    },
    "physics": {
        "title": "Case Study: Tacoma Narrows Bridge Collapse",
        "bullets": [
            "In 1940, the Tacoma Narrows Bridge twisted apart in a 40 mph wind months after opening.",
            "Wind drove its deck into a growing oscillation the structure couldn't withstand.",
            "The collapse, captured on film, reshaped how engineers treat aerodynamics and resonance.",
            "It brings the forces and oscillations in this module vividly to life.",
        ],
        "source": {"title": "Tacoma Narrows Bridge (1940)",
                   "url": "https://en.wikipedia.org/wiki/Tacoma_Narrows_Bridge_(1940)"},
    },
    "chemistry": {
        "title": "Case Study: Bhopal Disaster",
        "bullets": [
            "In 1984, a pesticide plant in Bhopal, India leaked a cloud of toxic methyl isocyanate gas.",
            "Thousands died and hundreds of thousands were injured in one of history's worst industrial disasters.",
            "Failed safety systems turned a chemical hazard into catastrophe.",
            "It underlines why understanding the chemistry in this module matters.",
        ],
        "source": {"title": "Bhopal disaster", "url": "https://en.wikipedia.org/wiki/Bhopal_disaster"},
    },
    "statistics": {
        "title": "Case Study: 1936 Literary Digest Poll",
        "bullets": [
            "In 1936, the Literary Digest polled millions and predicted Alf Landon would beat Roosevelt.",
            "Roosevelt won in a landslide — the magazine's enormous sample was badly biased.",
            "It had surveyed car and telephone owners, wealthier than the electorate at large.",
            "It's the classic lesson in sampling that this module's methods address.",
        ],
        "source": {"title": "The Literary Digest",
                   "url": "https://en.wikipedia.org/wiki/The_Literary_Digest"},
    },
}

# Computing/STEM fallback when a STEM module matches no specific domain — still a
# specific, real, well-documented event (never fabricated).
DEFAULT = {
    "title": "Case Study: Mars Climate Orbiter",
    "bullets": [
        "In 1999, NASA lost the $327 million Mars Climate Orbiter just as it reached the planet.",
        "One software module worked in metric units while another used imperial — and nobody caught it.",
        "The tiny mismatch sent the craft too close to Mars, where it broke apart.",
        "It is a powerful reminder that small technical details — the kind this module covers — really matter.",
    ],
    "source": {"title": "Mars Climate Orbiter",
               "url": "https://en.wikipedia.org/wiki/Mars_Climate_Orbiter"},
}

# Subject-neutral fallback for any non-STEM module that matches no field — a real,
# broadly motivating turning point that fits humanities and social sciences too.
DEFAULT_GENERAL = {
    "title": "Case Study: Gutenberg's Printing Press",
    "bullets": [
        "Around 1440, Johannes Gutenberg introduced movable-type printing to Europe.",
        "Books became cheap and plentiful, spreading ideas faster than ever before.",
        "It helped fuel the Reformation, the Scientific Revolution, and mass literacy.",
        "It's a reminder of how the knowledge in this module can reshape the world.",
    ],
    "source": {"title": "Printing press", "url": "https://en.wikipedia.org/wiki/Printing_press"},
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
    "psychology": (
        "psycholog", "cognitive", "behavioral", "behavioural", "mental health",
        "neuroscience", "perception",
    ),
    "biology": (
        "biolog", "genetic", "dna", "evolution", "organism", "ecology",
        "physiology", "anatomy", "medicine", "medical", "pharmacolog", "cell biology",
    ),
    "economics": (
        "econom", "macroeconom", "microeconom", "fiscal", "monetary", "gdp", "inflation",
    ),
    "physics": (
        "physics", "mechanics", "thermodynamic", "quantum", "relativity",
        "electromagnet", "kinematics",
    ),
    "chemistry": (
        "chemistry", "chemical", "organic chem", "molecule", "compound", "stoichiometry",
    ),
    "statistics": (
        "statistic", "probability", "regression", "sampling", "hypothesis test", "distribution",
    ),
}
# Specific domains first; ties broken by this order (most specific / dramatic).
_ORDER = (
    "security", "ml_ai", "os_concurrency", "databases", "web", "algorithms",
    "psychology", "biology", "economics", "physics", "chemistry", "statistics",
)

# Computing/STEM words that route an otherwise-unmatched module to the STEM
# default (Mars Climate Orbiter) rather than the subject-neutral one.
_STEM_HINTS = frozenset("computer engineering robotics technology informatics".split())


def case_study_for(title, objectives=""):
    """The best-matching curated case study for a module. Always returns one
    (title, bullets, source): a matched field, else a STEM default for
    computing/engineering modules, else a subject-neutral default — so every
    deck carries exactly one, per the spec, with no fabricated events."""
    text = f"{title} {objectives}".lower()
    best, best_score = None, 0
    for domain in _ORDER:
        score = sum(1 for keyword in _MATCHERS[domain] if keyword in text)
        if score > best_score:
            best, best_score = domain, score
    if best:
        return CASE_STUDIES[best]
    tokens = set(re.findall(r"[a-z0-9+#]+", text))
    if tokens & _PROGRAMMING_TERMS or tokens & _STEM_HINTS:
        return DEFAULT
    return DEFAULT_GENERAL
