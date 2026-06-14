# Course Schedule Builder

Paste a college course description, set the number of weeks in the term, and
get a weekly topic schedule that satisfies the description — built **without
any LLM/AI services**. No API keys, no usage-based costs, ever.

## How it works

Everything is classical, rule-based information retrieval:

1. **Description parsing** ([knowledge/schedule.py](knowledge/schedule.py)) —
   the course subject is resolved against a lexicon (earliest match wins:
   descriptions lead with their subject), and explicitly required topics are
   extracted from "covering X, Y, and Z"-style phrases.
2. **Curriculum retrieval** ([knowledge/curriculum.py](knowledge/curriculum.py)) —
   deterministic page lookups (no fragile keyword search) against free,
   keyless MediaWiki APIs:
   | Source | Pages fetched | Role |
   |---|---|---|
   | Wikiversity | "Python Programming", "Introduction to Psychology", ... | complete ordered course curricula |
   | Wikibooks | textbook landing pages | chapter TOCs for corroboration |
   | Wikipedia | "Outline of X" pages | topical guides for corroboration |
3. **Topic aggregation** — list items are harvested from curriculum-shaped
   sections, near-duplicates merged (Jaccard similarity), and ranked by
   cross-source corroboration. Uncorroborated items from link-farm pages are
   dropped; alphabetical catalogs are detected (their order carries no
   pedagogy) and sampled for breadth.
4. **Ordering & weaving** — topics are ordered by their consensus position in
   the source curricula (where they appear in real courses). Topics the
   description requires are guaranteed: unmatched ones are woven in using
   their order within the description.
5. **Week allocation** — topics are distributed across the term: contiguous
   groups when topics outnumber weeks; spanned topics ("X (continued)"),
   a midterm review, and a final review week when weeks outnumber topics.

Results are cached in memory for an hour. Confidence is "high" when 2+
independent sources corroborate the curriculum, "medium" for one, "low" when
the schedule comes only from the description itself.

## Copilot prompt endpoint

`POST /api/v1/copilot-prompt` is the "schedule → Copilot → materials" bridge:
give it a schedule (CSV or plain text) and it returns a ready-to-paste GitHub
Copilot Agent-mode prompt that scaffolds a full student project repository.
Like everything here it is **deterministic and LLM-free** — same input yields
byte-identical output, no provider or API key for any model involved.

[knowledge/copilot.py](knowledge/copilot.py) parses the schedule, classifies
each week (instructional / review / exam by regex), infers the course
language + domain from keywords (overridable via `language` / `projectTheme`),
maps weeks to `assignmentN` / `reviewN` / `examN` folders, and renders a fixed
template. Request: `{ "schedule": "...", "fileName"?, "language"?, "projectTheme"? }`
→ `{ "prompt", "language", "weeks" }`.

```sh
curl -X POST http://localhost:5050/api/v1/copilot-prompt \
  -H "Content-Type: application/json" \
  -d '{"schedule": "Week,Dates,Topics,Assignment\n1,\"Aug 17 – Aug 21\",\"Variables\",\"\""}'
```

## Module lecture generator

Paste a module's learning objectives — in **any format** (a list, or prose like
"students will be able to define X, explain Y…") — and get a PowerPoint where,
for each objective, there's an explanation slide plus worked-example slide(s),
with talking points and source citations in the speaker notes. Zero AI: every
slide is extracted from cited sources.

`knowledge/lecture.py`:
- `parse_objectives` is format-agnostic (inline numbered/bulleted lists, lead-in
  prose, run-on action-verb sentences, or a single objective).
- **Curated content first** ([knowledge/concept_library.py](knowledge/concept_library.py)):
  common programming concepts (Variables, Data Types, Loops, Conditionals,
  Functions, Classes…) and intro-CS topics (Real-World CS, Problem-Solving,
  Algorithms…) have hand-written, plain-English explanations and clean canonical
  code — so a Python intro module reads like a polished, instructor-made deck
  with no LLM. Anything not curated falls back to retrieval
  (`select_sources`/`fetch` → BM25 `rank` → extractive `synthesize`), with
  encyclopedic markup (LaTeX `{\displaystyle …}`, citation residue) stripped by
  `sanitize_layman`. The fallback queries **Simple English Wikipedia**
  alongside regular Wikipedia — its Basic-English prose (short sentences,
  common words) competes sentence-for-sentence in ranking, so the plainest
  phrasing tends to win when a topic has both.
- A deck's structure follows its **profile** (`classify_subject`): `programming`
  (per-concept code units) or `conceptual` (everything else — sciences, social
  science, humanities). The profile is deterministic (title/objective keywords),
  no model.
- Slide 3 of every deck is a **real-world case study**
  ([knowledge/case_study.py](knowledge/case_study.py)): a curated, *source-backed*
  incident chosen deterministically by matching the module to a domain — across
  computing (e.g. the 2017 Equifax breach) **and** academic fields (psychology →
  the Stanford Prison Experiment, biology, economics, physics, chemistry,
  statistics) — with a STEM default (Mars Climate Orbiter) and a subject-neutral
  default (Gutenberg's printing press) so every deck gets exactly one. No LLM
  means no hallucinated or misdated events — each is a documented incident, cited
  (Wikipedia) in the speaker notes.
- For a **programming** lecture, each programming concept the lecture covers
  gets a fixed **four-slide unit** — `Example:` → `Walkthrough:` → `Practice:`
  → `Answer:` — right after its concept slide, de-duplicated to the first
  objective that names it:
  - **Example** — a correct, self-contained snippet (curated clean code, else
    fetched) with a one-line caption.
  - **Walkthrough** — the *same* code, two-column, with a line-by-line
    explanation beside it.
  - **Practice** — a small challenge (1–2 task bullets) on the same concept.
    The code shown is the **Example snippet verbatim**, a read-only reference —
    never starter code and never the solution.
  - **Answer** — a *distinct*, runnable solution to that challenge.

  Only the four unit slides carry code (concept/title/reference slides never
  do); the single reference snippet is the Example's code, reused by the
  Walkthrough and Practice slides *by construction*, so a generated practice
  snippet can never leak the answer.
- For a **conceptual** lecture (any non-programming subject), each objective
  instead gets, after its concept slide: an **`Illustration:`** slide (a real,
  cited "for example…" pulled from the sources, when one is found) and a
  **`Check Your Understanding:`** slide of deterministic review questions
  (define → explain → apply → relate-to-the-next-topic), with model answers and
  citations in the speaker notes. No code, no LLM — the questions are templated
  from each objective's topic.

Every returned deck (this endpoint and the per-unit lectures in
`/api/v1/materials`) is built to one house style in
[knowledge/slides.py](knowledge/slides.py), modeled on a polished reference
deck: 16:9, a navy header band with a white title, a light background, a
bright-blue accent, dark code blocks (light monospace + a blue language label),
Title-Cased self-contained titles, and up to six short layman bullets per
content slide (overflow → speaker notes; agenda/reference lists use a compact
non-bullet slide).

```sh
curl -X POST http://localhost:5050/api/v1/lecture \
  -H "Content-Type: application/json" \
  -d '{"title": "Intro to Python", "objectives": "Students will be able to define variables, explain control flow, and write functions."}' \
  --output module-lecture.pptx
```

## Course materials generator

After Copilot generates the project repository from the prompt, upload its zip
back into the app ("Generate course materials") and get — with zero AI:

- `lectures/week-NN-*.pptx` — a slide deck per unit, built from the teaching
  comments in each unit's starter code
- `lms/week-NN-*.docx` — a weekly LMS introduction per unit, Word-formatted
  with hierarchical heading styles
- `assignments/week-NN-*.docx` — assignment instructions per week (Word,
  same professional heading hierarchy)
- `rubric.csv` — a deterministic rubric for a **non-LLM grader API**: one row
  per criterion, every criterion a mechanical check (pytest results,
  placeholder lines absent, file compiles, files present) with weights
  summing to 100 per unit; leading `GRADER_CONTRACT` rows document how to
  evaluate each criterion type; multi-value cells are `|`-separated

The parser ([knowledge/materials.py](knowledge/materials.py)) expects the
structure the Copilot prompt produces: unit folders containing
`INSTRUCTIONS.md`, starter code, and `test_*.py` contract tests. Units are
ordered assignments-first (numeric), then review/exam pairs, then the final.

Note: Vercel caps request bodies around 4.5 MB — large project zips upload
fine locally but may need slimming (drop `node_modules`/binaries) for the
deployed endpoint.

## Run it locally

```sh
pip install -r requirements.txt
python app.py            # dev server on http://localhost:5050 (or set PORT)
```

## API

The HTTP surface ([service.py](service.py)) is versioned under `/api/v1`; the
domain logic stays in `knowledge/`. A self-describing OpenAPI spec is served at
`/api/v1/openapi.json`, and the bundled UI includes an API console for testing.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | no | liveness/version |
| GET | `/api/v1/openapi.json` | no | OpenAPI 3.1 contract |
| POST | `/api/v1/schedule` | yes* | course description → weekly schedule (JSON) |
| POST | `/api/v1/copilot-prompt` | yes* | schedule (CSV/text) → GitHub Copilot project prompt (JSON) |
| POST | `/api/v1/lecture` | yes* | module objectives → PowerPoint lecture (`.pptx`) |
| POST | `/api/v1/materials` | yes* | project zip → materials zip (`application/zip`) |

The unversioned `/api/schedule` and `/api/materials` remain as deprecated
aliases. \*Auth is **optional**: required only when the `API_KEY` env var is
set (see below).

`POST /api/v1/schedule` takes `description` and `weeks` (required), plus three
optional fields — all backward compatible (omit them for the original behavior):

- `startDate` (ISO `YYYY-MM-DD`) — adds a Mon–Fri `dates` range to each week.
- `tests` (integer ≥ 0) — places that many exams evenly across the term, each
  preceded by a review week; both count toward the total `weeks` (no extras).
- `term` (string) — a label echoed back in the response.

```sh
curl -X POST http://localhost:5050/api/v1/schedule \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"description": "An intro Python course covering variables and functions", "weeks": 14, "startDate": "2026-08-24", "tests": 2, "term": "Fall 2026"}'
```

Success returns the resource directly (schedule JSON, or the binary file for
lecture/materials). Each week carries `topics`, `assignment`, and `kind`
(`instruction` | `review` | `exam`), plus `dates` when `startDate` was given:

```json
{
  "subject": "Python",
  "confidence": "high",
  "term": "Fall 2026",
  "weeks": [
    {"week": 1, "dates": "Aug 24 – Aug 28", "topics": ["Introduction", "Variables"],
     "assignment": "Exercises: Introduction, Variables", "kind": "instruction"},
    {"week": 6, "dates": "Sep 28 – Oct 2", "topics": ["Review"],
     "assignment": "Review prior material and complete the practice set", "kind": "review"},
    {"week": 7, "dates": "Oct 5 – Oct 9", "topics": ["Exam"], "assignment": "Test", "kind": "exam"}
  ],
  "topics": [{"name": "Variables", "citations": [1, 2], "position": 0.05}, ...],
  "citations": [{"title": "Python Programming", "url": "...", "source": "Wikiversity"}]
}
```

Errors always use one envelope, with the matching HTTP status:

```json
{"error": {"code": "invalid_request", "message": "Please provide a course description."}}
```

### Configuration (env vars)

| Var | Effect |
|---|---|
| `API_KEY` | If set, protected endpoints require it via `X-API-Key` (or `Authorization: Bearer`). If unset, the API is open — convenient for local dev. |
| `CORS_ORIGINS` | Allowed origins, comma-separated. Default `*`. When a list is given, only matching `Origin`s are echoed back. |
| `PORT` | Local dev port (default 5050). |
| `LOG_LEVEL` | Access-log level (default `INFO`). |
| `LOG_PAYLOADS` | Capture request/response JSON bodies in the access log (default on; set `0` to log metadata only). |
| `LOG_PAYLOAD_MAX_BYTES` | Truncate captured bodies to this many bytes (default `4096`). |
| `ARCHIVE_ARTIFACTS` | Store generated `.pptx`/`.zip` to Vercel Blob (default on; set `0` to disable). |
| `BLOB_READ_WRITE_TOKEN` | Auto-provisioned when you enable **Storage → Blob** on the Vercel project; required for artifact archiving. Unset locally → archiving is skipped gracefully. |

CORS is enabled (cross-origin clients are supported); the API key travels in a
header, never a cookie.

### Logging & generated artifacts

Every request emits one structured JSON line to stdout
([observability.py](observability.py)), which Vercel surfaces in **Runtime Logs
/ Observability** (filterable by field): method, path, status, duration, sizes,
client IP, `api_key_present` (the key value is **never** logged), and the
request/response JSON bodies (capped + redacted; binary `.pptx`/`.zip` bodies
are logged by size only).

Generated lectures and material bundles are archived to **Vercel Blob**
([knowledge/artifacts.py](knowledge/artifacts.py)) — no new dependency (REST via
`requests`) — and the stored URL is attached to that request's log line. Browse
them via the authed `GET /api/v1/artifacts` (newest first, with each file's
request metadata) or the **Generated artifacts** panel in the UI. To enable it,
turn on **Storage → Blob** for the Vercel project (provisions
`BLOB_READ_WRITE_TOKEN`); until then everything runs and just reports
`"enabled": false`. Set `API_KEY` so stored artifacts aren't world-listable. A
`.pptx` URL downloads the exact file (open in PowerPoint/Slides); in-browser
slide rendering isn't included.

## Tests

Unit tests run on canned fixtures — no network required:

```sh
pip install -r requirements-dev.txt
python -m pytest
```

## Deploy (Vercel)

Vercel natively detects Flask: `app.py` at the repo root exposing the WSGI
`app` variable is the entrypoint. No `vercel.json`, no `api/` directory, no
config. The Framework Preset in Project → Settings should show **Flask**
(set it manually if the project was created as "Other").

Two Vercel-specific rules this repo follows:

- Static assets live in `public/**` — served by Vercel's CDN. Flask's
  `static_folder` must NOT be relied on in production: `public/` is not
  bundled into the function. Locally Flask serves the same folder; in
  production the `/` route falls back to redirecting to `/index.html`.
- Native Flask detection requires **Vercel CLI ≥ 48.2.10** (`npm i -g
  vercel@latest`). Older CLIs won't recognize the app and everything 404s.

```sh
npm i -g vercel@latest
vercel          # preview deploy
vercel --prod   # production
```

Set `API_KEY` (and optionally `CORS_ORIGINS`) under Project → Settings →
Environment Variables to lock down the deployed API. Two further caveats:
Vercel caps request bodies around **4.5 MB**, so large project zips that work
locally may fail `POST /api/v1/materials` on the deployed function (slim the
zip, or move to a direct-to-blob upload); and because each serverless instance
is independent, true global rate limiting needs an external store (e.g. Vercel
KV) — the API key is the abuse gate, with a per-instance outbound throttle in
[knowledge/sources/base.py](knowledge/sources/base.py) protecting the upstream
APIs.

## Under the hood

The schedule builder sits on a general LLM-free retrieval engine
([knowledge/](knowledge)): rule-based query analysis, parallel fetch from
trusted keyless APIs, hand-rolled BM25 sentence ranking, and extractive
synthesis. The curriculum path bypasses keyword search entirely in favor of
deterministic page titles — corroboration across independent published
curricula is the ranking signal.
