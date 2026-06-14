"""Deterministic schedule -> GitHub Copilot project prompt.

No LLM, no network: parse the schedule (CSV or plain text), classify each week,
infer the course language/domain from keywords, and render a fixed template.
Same input -> byte-identical output."""

import csv
import io
import re


class CopilotError(ValueError):
    """User-facing problem with the schedule input."""


PROFILES = {
    "python": {
        "language": "Python",
        "domain": "data science",
        "theme": "a data-analysis pipeline with an interactive dashboard",
        "ext": "py",
        "editable": "solution.py",
        "test": "test_solution.py",
        "keywords": [
            "python", "pandas", "numpy", "dataframe", "jupyter", "matplotlib",
            "tuple", "dictionar", "list comprehension", "pip", "virtualenv",
        ],
    },
    "javascript": {
        "language": "JavaScript",
        "domain": "web development",
        "theme": "a full-stack web application",
        "ext": "js",
        "editable": "solution.js",
        "test": "solution.test.js",
        "keywords": [
            "javascript", "typescript", "react", "node", "npm", "dom",
            "express", "frontend", "web app", "fetch", "async",
        ],
    },
    "java": {
        "language": "Java",
        "domain": "enterprise / Android software",
        "theme": "an enterprise-style application",
        "ext": "java",
        "editable": "Solution.java",
        "test": "SolutionTest.java",
        "keywords": [
            "java", "spring", "android", "jvm", "maven", "gradle",
            "object-oriented", "oop", "interface", "inheritance",
        ],
    },
    "r": {
        "language": "R",
        "domain": "statistics / data analysis",
        "theme": "a statistical analysis report with visualizations",
        "ext": "R",
        "editable": "solution.R",
        "test": "test_solution.R",
        "keywords": [
            "ggplot", "tidyverse", "dplyr", "regression", "statistic",
            "r markdown", "data frame",
        ],
    },
    "sql": {
        "language": "SQL",
        "domain": "data engineering",
        "theme": "a relational database with a query and reporting layer",
        "ext": "sql",
        "editable": "solution.sql",
        "test": "test_solution.sql",
        "keywords": [
            "sql", "relational", "database", "query", "join", "schema",
            "normaliz", "postgres", "mysql", "data model",
        ],
    },
}
DEFAULT_PROFILE = "javascript"

_REVIEW_RE = re.compile(r"\breview\b", re.I)
_EXAM_RE = re.compile(r"\b(exam|midterm|final|quiz|test|assessment)\b", re.I)

COPILOT_TEMPLATE = """Build a complete, ready-to-teach student software project repository in {LANGUAGE} for a {DOMAIN} course. The project is {THEME}, themed around employer-relevant skills so students can showcase it to prospective employers. It must include a web frontend deployed to Vercel and be buildable by a beginner over a {WEEK_COUNT}-week term with zero DevOps experience.

Tech stack rules:
- Use a simple stack that deploys to Vercel out of the box. Prefer Next.js for full-stack or data-heavy courses, or a plain HTML/CSS/JavaScript static site for lighter ones. First evaluate whether the course goals can be met with Next.js, Vercel, and GitHub alone (static data, local state, file-based storage, or Vercel Edge/API routes). Only add other services if genuinely required (e.g. a persistent relational database, real-time data, or cross-user auth). When needed, prefer free tiers that integrate natively with Vercel and GitHub, such as Supabase. Avoid anything needing DevOps, paid plans at student scale, or setup beyond clicking "Connect to Vercel".

Repository structure:
- A single root-level "assignments/" directory containing every assignment folder. No assignment folder may exist outside it.
- A web frontend (in the same repo) deployed to Vercel.
- A README describing the project, the week-by-week plan, and which weeks are review/exam weeks and the topics they assess.

Week-by-week plan (create exactly these folders, in this order):
{WEEK_PLAN_LINES}

Rules that apply to EVERY assignment, review, and exam folder:
- Exactly ONE file in the folder is edited by students to complete the work; name it `{EDITABLE}`. All other files are read-only scaffolding.
- An INSTRUCTIONS.md with verbose, beginner-friendly instructions and several worked examples that illustrate the concepts WITHOUT giving away the solution (use different scenarios/data than the actual tasks).
- Unit tests (`{TEST}`) that verify the student's implementation and import/require ONLY `{EDITABLE}`.
- All instructions throughout every INSTRUCTIONS.md must use the GitHub and GitHub Codespaces graphical interfaces (Source Control panel to commit and push, Testing panel to run tests, the GitHub website for pull requests and merging) rather than terminal commands wherever possible. Any step doable through a UI must be described through the UI and must NOT tell students to open the terminal.
- Completing the single editable file - and nothing else - must automatically unlock that assignment's feature on the frontend. Students must never edit config, env vars, feature flags, or any file outside their assignment folder. The frontend must directly import or dynamically read only the student's `{EDITABLE}` (e.g. import the module and check whether its exported function/class returns non-trivial output, or read a value the student set), and update the UI when that check passes. Specify the exact import/read path for each assignment file, what the frontend checks, and how the UI changes when it passes. No manual wiring step is ever required of the student.

assignment0 (onboarding) must walk students step by step through: (1) forking the repository, (2) deploying the fork to Vercel and getting a live preview URL, (3) creating a new branch, (4) opening the branch in GitHub Codespaces, (5) making a simple code change (e.g. changing a variable in `{EDITABLE}` to their own name so it appears in the frontend), (6) running assignment0's unit tests via the Testing panel in Codespaces (not the terminal), (7) committing via the Source Control panel (not the terminal), (8) pushing via the Source Control panel (not the terminal), (9) opening a pull request on the GitHub website, (10) verifying the Vercel preview deployment on the PR, (11) merging the PR on the GitHub website. Put these in assignments/assignment0/INSTRUCTIONS.md.

Review folders (reviewN) must contain: an INSTRUCTIONS.md review guide and study materials stating exactly which prior topics and assignments are covered, one editable file `{EDITABLE}`, unit tests, and the same frontend-unlock wiring. Follow the no-terminal rule.

Exam folders (examN) must contain: an INSTRUCTIONS.md describing the topics assessed plus a practice exercise mirroring the exam format, one editable file `{EDITABLE}`, unit tests, and the same frontend-unlock wiring. The README must note these weeks and their topics. Follow the no-terminal rule.

Deliverable: scaffold the entire repository now - the top-level file structure, every assignment folder with all files named above, the frontend and how it is structured, the Vercel configuration, the frontend-unlock mechanism for each assignment, and the README. Cover every topic in the plan in order."""


def parse_schedule(text):
    """Ordered [{week, dates, topics, assignment}] from CSV or plain text."""
    try:
        reader = list(csv.reader(io.StringIO(text)))
    except Exception:
        reader = []

    header_idx = None
    cols = {"week": 0, "dates": 1, "topics": 2, "assignment": 3}
    for index, row in enumerate(reader):
        joined = ",".join(cell.lower() for cell in row)
        if "week" in joined and ("topic" in joined or "assignment" in joined):
            header_idx = index
            for position, cell in enumerate(row):
                name = cell.strip().lower()
                if name.startswith("week"):
                    cols["week"] = position
                elif name.startswith("date"):
                    cols["dates"] = position
                elif name.startswith("topic"):
                    cols["topics"] = position
                elif name.startswith("assign"):
                    cols["assignment"] = position
            break

    rows = []
    if header_idx is not None:
        for row in reader[header_idx + 1:]:
            if not any(cell.strip() for cell in row):
                continue

            def get(key, row=row):
                position = cols[key]
                return row[position].strip() if position < len(row) else ""

            digits = re.sub(r"\D", "", get("week"))
            rows.append(
                {
                    "week": int(digits) if digits else len(rows) + 1,
                    "dates": get("dates"),
                    "topics": get("topics"),
                    "assignment": get("assignment"),
                }
            )
    else:
        # Not CSV-shaped: one week per non-empty line, the whole line is the topic.
        for index, line in enumerate(l.strip() for l in text.splitlines() if l.strip()):
            rows.append({"week": index + 1, "dates": "", "topics": line, "assignment": ""})
    return rows


def classify(row):
    """exam | review | instructional, from the week's topic + assignment text.
    Exam is checked first so 'Exam Review' / 'final assessment' count as exam."""
    text = f"{row['topics']} {row['assignment']}"
    if _EXAM_RE.search(text):
        return "exam"
    if _REVIEW_RE.search(text):
        return "review"
    return "instructional"


def infer_language(rows, file_name=None, override=None):
    """Best-matching profile key. An override (already validated) wins; otherwise
    the profile with the most keyword hits, defaulting to JavaScript."""
    if override:
        return override if override in PROFILES else None
    blob = (file_name or "").lower() + " " + " ".join(
        f"{row['topics']} {row['assignment']}".lower() for row in rows
    )
    best, best_score = DEFAULT_PROFILE, 0
    for key, profile in PROFILES.items():
        score = sum(blob.count(keyword) for keyword in profile["keywords"])
        if score > best_score:
            best, best_score = key, score
    return best


def build_prompt(rows, profile, theme):
    """Render the Copilot prompt from the fixed template."""
    assignments = reviews = exams = 0
    lines = [
        f"- assignment0: Onboarding (fork, deploy, edit, test, commit, push, PR, merge). "
        f"Edit {profile['editable']}."
    ]
    for row in rows:
        kind = classify(row)
        if kind == "instructional":
            assignments += 1
            folder = f"assignment{assignments}"
            label = f"Topic: {row['topics'] or '(unspecified)'}"
        elif kind == "review":
            reviews += 1
            folder = f"review{reviews}"
            label = f"Review of: {row['topics'] or 'prior topics'}"
        else:
            exams += 1
            folder = f"exam{exams}"
            label = f"Assessment: {row['topics'] or 'cumulative'}"
        dates = f" ({row['dates']})" if row["dates"] else ""
        lines.append(
            f"- Week {row['week']}{dates} {folder} - {label}. "
            f"Edit {profile['editable']}; tests in {profile['test']}."
        )

    return COPILOT_TEMPLATE.format(
        LANGUAGE=profile["language"],
        DOMAIN=profile["domain"],
        THEME=theme,
        WEEK_COUNT=len(rows),
        WEEK_PLAN_LINES="\n".join(lines),
        EDITABLE=profile["editable"],
        TEST=profile["test"],
    )


def build_copilot_prompt(schedule, file_name=None, language=None, project_theme=None):
    """The /api/v1/copilot-prompt entry point. Returns
    {prompt, language, weeks}; raises CopilotError when no weeks parse."""
    rows = parse_schedule(schedule)
    if not rows:
        raise CopilotError("Could not parse any weeks from 'schedule'.")

    lang = infer_language(rows, file_name, language) or DEFAULT_PROFILE
    profile = PROFILES[lang]
    theme = (
        project_theme.strip()
        if isinstance(project_theme, str) and project_theme.strip()
        else profile["theme"]
    )
    return {
        "prompt": build_prompt(rows, profile, theme),
        "language": lang,
        "weeks": len(rows),
    }
