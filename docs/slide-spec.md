# Lecture slide specification

The contract the lecture deck generator follows. The `/api/v1/lecture` endpoint
(and the per-unit lectures in `/api/v1/materials`) emit `.pptx` directly; this
document is the conceptual model those decks are built to. Implemented in
[knowledge/lecture.py](../knowledge/lecture.py),
[knowledge/slides.py](../knowledge/slides.py), and
[knowledge/concept_library.py](../knowledge/concept_library.py).

## 1. Slide object shape

```jsonc
{
  "title": "string",            // required
  "bullets": ["string", ...],   // required (may be empty array)
  "code": "string",             // optional; raw source with real newlines
  "codeLanguage": "string"      // optional; e.g. "python", "javascript"
}
```

A deck is `{ "presentationTitle": "string", "slides": [ ... ] }`.

## 2. Deck-level ordering

1. **Title slide.** The module title.
2. **Module Overview.** Lists the key topics/objectives. No code.
3. **Case Study** (§2a). One real-world case study, before any concept slides.
4. **Body.** Walk the objectives in order. Each objective produces a **concept
   slide** (prose, no code); if that concept is a coding concept, the concept
   slide is **immediately followed by a fixed 4-slide unit** (§3).
5. Non-coding concepts produce just the concept slide (no unit).
6. (Optional) a references/sources slide at the end.

```
Slide 1: Title
Slide 2: Module Overview
Slide 3: Case Study
Slide 4+: body
   programming objective: Concept → Example → Walkthrough → Practice → Answer
   conceptual objective:  Concept → Illustration → Check Your Understanding
(optional) References / sources
```

## 2a. The case-study slide

Exactly **one** case-study slide per deck, placed right after the overview and
before any concept slides. It motivates the module with a real, well-known
event. Applies to **every** deck — coding or not; there is no conditional skip.

- **Title** must begin with the literal prefix `Case Study:` (a role marker,
  like `Example:` / `Walkthrough:` / `Practice:` / `Answer:`), followed by a
  short event name — e.g. `Case Study: 2017 Equifax Breach`.
- **Bullets** describe a specific, real, widely-documented event about the
  module's subject: who (organization/product) and roughly when (year/era),
  what happened, and a final bullet that ties the story to what students are
  about to learn. Preference: a dramatic cautionary failure/breach over an
  impressive build (failures motivate fundamentals best). Same bullet budget as
  the rest of the deck (≤4 on the lecture path).
- **No code.** It renders as an ordinary no-code bullets slide.
- **Factual integrity.** Never invent or misdate an event.

**How this engine does it (deterministic, source-backed).** Unlike an LLM —
which can hallucinate or misdate events and can't synthesize a real story after
the fact — the Course Engine selects from a curated library of real incidents
([knowledge/case_study.py](../knowledge/case_study.py)). The module's title +
objectives are matched against domain keywords across computing (security,
ML/AI, OS/concurrency, databases, web, algorithms) **and** academic fields
(psychology, biology, economics, physics, chemistry, statistics). An unmatched
module falls back to a STEM default (Mars Climate Orbiter) for
computing/engineering subjects, otherwise a subject-neutral default (Gutenberg's
printing press), so every deck gets exactly one. Each case study carries a real
Wikipedia citation, surfaced in the slide's speaker notes.

## 3. The coding-concept unit

A coding concept (loop, conditional, variable, function, class, data structure,
etc.) MUST be followed *immediately* by exactly these four slides, in this exact
order:

| # | Title prefix   | Purpose                                                   | `code` content                                | `bullets`                          |
|---|----------------|-----------------------------------------------------------|-----------------------------------------------|------------------------------------|
| 1 | `Example:`     | Demonstrate the concept with a correct, self-contained snippet | **The worked example** (+ `codeLanguage`)     | ≤1 short caption                   |
| 2 | `Walkthrough:` | Explain that example **line by line**                     | **Identical to the Example's code**           | Line-by-line explanation (several) |
| 3 | `Practice:`    | Pose a simple coding challenge on the same concept        | **Identical to the Example's code** — reference only | 1–2 bullets stating the task |
| 4 | `Answer:`      | Correct, runnable solution to *that* practice challenge   | **Its own distinct solution code** (+ `codeLanguage`) | ≤1 caption                  |

Pattern per coding concept:

```
Concept (no code) → Example → Walkthrough → Practice → Answer
```

Title prefixes (`Example:`, `Walkthrough:`, `Practice:`, `Answer:`) are
significant — downstream logic uses them to identify slide roles.

## 4. Code-attachment rules

- **Concept / title / references slides: never carry code.**
- **All four unit slides carry `code` + `codeLanguage`.** None of
  Example/Walkthrough/Practice may be left codeless.
- **There is exactly one "reference snippet" per concept: the Example's code.**
  The **Walkthrough** and the **Practice** slides BOTH display that *same*
  reference snippet, verbatim.
  - The Practice slide's code is a **read-only reference**, giving students a
    worked example to consult while they attempt the challenge.
  - **The Practice slide must NOT contain the solution to its challenge, a
    partial/starter version of the solution, or any code that reveals the
    answer.** It is *not* "modified starter code" — it is the unchanged Example
    snippet.
- **Only the Answer slide carries the solution** to the practice challenge, as
  its own distinct code (different from the reference snippet).
- **Enforcement.** The generator builds Example, Walkthrough, and Practice from
  the *same* example code object, so the reference snippet is reused **by
  construction** — a generated practice snippet can never leak the answer. (A
  post-hoc equivalent: scan slides in order, remember the most recent
  `Example:` code, and overwrite each following `Walkthrough:`/`Practice:`
  slide's code with it — a hard override, never "fill if missing." Never touch
  `Answer:` slides.)

## 5. Bullet limits

- Small counts: up to ~3–4 bullets on most slides; each bullet is one
  self-contained idea.
- The Walkthrough legitimately uses its full budget for the line-by-line
  explanation.

## 6. Non-programming (conceptual) modules

A module that teaches no programming uses the **conceptual profile**: no
`code`/`codeLanguage` anywhere, and the Example/Walkthrough/Practice/Answer unit
is replaced by a parallel rhythm after each concept slide:

| Title prefix    | Purpose                                                        | `bullets`                                  |
|-----------------|---------------------------------------------------------------|--------------------------------------------|
| `Illustration:` | A concrete real-world example of the concept                  | one retrieved, cited "for example…" sentence (omitted if none found) |
| `Check Your Understanding:` | Review questions on the concept                    | deterministic prompts (define → explain → apply → relate); model answers + sources in the speaker notes |

The questions are templated from the objective's topic (no LLM); the "relate"
question links it to the next objective's topic. The profile is chosen by
`classify_subject` (`programming` vs `conceptual`); quantitative subjects
currently use the conceptual profile.

## 7. Rendering (this repo)

The engine emits its own `.pptx` (it does not consume the JSON above), but the
house style mirrors it:

- **Code + ≥2 bullets** (the Walkthrough) → **two-column**: code left, bullets
  right, full height — avoids clipping.
- **Code + ≤1 caption / task** (Example / Practice / Answer) → **stacked**:
  caption (or task bullets) on top, full-width code panel below.
- **No code** (concept / title) → bullets use the full content area.

## 8. No-LLM note

Everything is deterministic. Curated concepts (see
[concept_library.py](../knowledge/concept_library.py)) ship a hand-authored,
fully distinct unit. For an *uncurated* concept whose example is retrieved from
the web, the walkthrough is derived line-by-line by a rule-based describer and
the practice reuses the example as its reference; with no LLM to author a fresh
solution, the fallback answer reuses the worked example.
