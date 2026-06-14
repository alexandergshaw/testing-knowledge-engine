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

1. **Slide 1 — Title / overview.** Lists the key topics/objectives. No code.
2. **Body.** Walk the objectives in order. Each objective produces a **concept
   slide** (prose, no code); if that concept is a coding concept, the concept
   slide is **immediately followed by a fixed 4-slide unit** (§3).
3. Non-coding concepts produce just the concept slide (no unit).
4. (Optional) a references/sources slide at the end.

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

## 6. Non-programming modules

If the module teaches no programming: omit `code`/`codeLanguage` everywhere and
omit the entire Example/Walkthrough/Practice/Answer unit — concept slides only.

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
