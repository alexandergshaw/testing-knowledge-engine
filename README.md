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

## Run it locally

```sh
pip install -r requirements.txt
python app.py            # dev server on http://localhost:5050 (or set PORT)
```

## API

```sh
curl -X POST http://localhost:5050/api/schedule \
  -H "Content-Type: application/json" \
  -d '{"description": "An introductory college course in Python programming, covering variables, functions, and object-oriented programming.", "weeks": 14}'
```

Response shape:

```json
{
  "subject": "Python",
  "confidence": "high",
  "weeks": [{"week": 1, "topics": ["Introduction", "Variables"]}, ...],
  "topics": [{"name": "Variables", "citations": [1, 2], "position": 0.05}, ...],
  "citations": [{"title": "Python Programming", "url": "...", "source": "Wikiversity"}]
}
```

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

## Under the hood

The schedule builder sits on a general LLM-free retrieval engine
([knowledge/](knowledge)): rule-based query analysis, parallel fetch from
trusted keyless APIs, hand-rolled BM25 sentence ranking, and extractive
synthesis. The curriculum path bypasses keyword search entirely in favor of
deterministic page titles — corroboration across independent published
curricula is the ranking signal.
