# Knowledge Engine

A Flask app that *feels* like asking an LLM a question — type a free-form
question, get back a synthesized prose answer with citations — built with
**zero LLM/AI services**. No API keys, no usage-based costs, ever.

## How it works

This is classic federated information retrieval, solved with pre-LLM
techniques:

1. **Query analysis** ([knowledge/query.py](knowledge/query.py)) — rule-based
   keyword extraction, topic isolation, and question-type classification
   (definition / how-to / why / person / generic).
2. **Domain routing** ([knowledge/pipeline.py](knowledge/pipeline.py)) —
   heuristics pick which sources to ask. Wikipedia and DuckDuckGo always run;
   Stack Overflow joins for programming-shaped questions; Wiktionary for
   short definition questions.
3. **Parallel fetch** — free, keyless public APIs queried concurrently:
   | Source | API | Domains |
   |---|---|---|
   | Wikipedia | MediaWiki search + extracts | history, psychology, science, general |
   | Wiktionary | MediaWiki extracts | word definitions |
   | Stack Overflow | api.stackexchange.com (keyless quota) | programming |
   | DuckDuckGo | Instant Answer API | quick facts, abstracts |
4. **Ranking** ([knowledge/ranking.py](knowledge/ranking.py)) — every fetched
   sentence is scored against the question with hand-rolled **BM25** (the
   algorithm behind classical search engines), weighted by source trust and
   lead-sentence position.
5. **Synthesis** ([knowledge/synthesize.py](knowledge/synthesize.py)) —
   extractive: top sentences are deduplicated (Jaccard similarity), ordered
   (definition-shaped opener first), grouped into paragraphs, and tagged with
   numbered citations. Weak retrieval yields an honest "I couldn't find solid
   information" instead of fabrication.

Results are cached in memory for an hour so repeat questions don't re-hit the
source APIs.

## Run it locally

```sh
pip install -r requirements.txt
python app.py            # dev server on http://localhost:5050 (or set PORT)
```

Or via the API directly:

```sh
curl "http://localhost:5000/api/ask?q=What is cognitive dissonance?"
```

Response shape:

```json
{
  "question": "What is cognitive dissonance?",
  "answer": "Cognitive dissonance is ... [1]\n\nFurther detail ... [2]",
  "citations": [{"title": "...", "url": "...", "source": "Wikipedia"}],
  "confidence": "high"
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
`app` variable is the entrypoint, and every route — including the static
files in `public/` — is handled by the app. No `vercel.json`, no `api/`
directory, no config. The Framework Preset in Project → Settings should show
**Flask** (set it manually if the project was created as "Other").

No timeout config is needed either: source fetching is capped at 10s
internally, well under Vercel's default function duration.

Two Vercel-specific rules this repo follows:

- Static assets live in `public/**` — served by Vercel's CDN. Per Vercel's
  docs, Flask's `static_folder` must NOT be relied on in production: `public/`
  is not bundled into the function. Locally Flask serves the same folder; in
  production the `/` route falls back to redirecting to `/index.html`, which
  the CDN serves.
- Native Flask detection requires **Vercel CLI ≥ 48.2.10** (`npm i -g
  vercel@latest`). Older CLIs won't recognize the app and everything 404s.

Deploy with the CLI, or just import the repo at vercel.com:

```sh
npm i -g vercel@latest
vercel          # preview deploy
vercel --prod   # production
```

Serverless notes: the app is fully stateless, so it scales horizontally for
free. The in-memory answer cache lives per warm instance — repeat questions
still get cached on a warm function, but a cold start begins empty. That only
costs latency, never money.

## Adding a knowledge source

1. Create `knowledge/sources/yoursource.py` subclassing `Source`
   ([knowledge/sources/base.py](knowledge/sources/base.py)): implement
   `search(query) -> list[Passage]` and set `name` and `trust`.
2. Instantiate it in `select_sources()` in
   [knowledge/pipeline.py](knowledge/pipeline.py), unconditionally (generalist)
   or behind a routing rule (specialist).

Misrouted sources are harmless — BM25 buries irrelevant results.
