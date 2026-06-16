# `POST /api/v1/lecture` — file uploads

The lecture endpoint accepts an uploaded artifact (most importantly a `.pptx`
deck) in addition to / instead of a typed `objectives` string. This document is
the contract for both API consumers and the maintainers of any calling app.

## Endpoint
`POST /api/v1/lecture` — hosted at
`https://testing-knowledge-engine.vercel.app/api/v1/lecture` (local dev:
`http://localhost:5050/api/v1/lecture`).

- **Auth:** optional. If the deployment sets `API_KEY`, send `X-API-Key: <key>`
  (or `Authorization: Bearer <key>`); otherwise the endpoint is open. Unchanged.
- **Response:** unchanged — `200` with the binary `.pptx`
  (`application/vnd.openxmlformats-officedocument.presentationml.presentation`,
  `Content-Disposition: attachment; filename="module-lecture.pptx"`). When a file
  was supplied, the deck's title slide notes "· from <filename>".

## Two accepted request shapes

**1. JSON (original — unchanged):**
```jsonc
Content-Type: application/json
{ "objectives": "string (required)", "title": "string (optional)" }
```

**2. multipart/form-data (added):**

| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | binary | one of `file`/`objectives` | The artifact to seed from. |
| `objectives` | string | optional when `file` present | Merged **after** the file's extracted text. |
| `title` | string | optional | Deck title + retrieval/language bias (as today). |
| `homework` | string | optional | Assignment text — adds prerequisite coverage (see "Homework" below). |
| `homeworkFile` | binary | optional | Assignment as a file; extracted to text, used the same as `homework`. |

`homework` is also accepted in the JSON body.

Rules (enforced server-side):
- At least one of `file` / `objectives` must be present.
- If both: extracted file text first, then `objectives`.
- If only `file`: objectives are derived entirely from the extracted text.
- Merged text is capped to ~4000 chars / ~20 objectives — long decks are
  summarized down to their headings/objectives, not used verbatim.
- One file per request.

## How it works (set expectations accordingly)
The endpoint is **deterministic / no-LLM**. The uploaded file is **not** free-form
LLM context — its text is extracted server-side
([knowledge/extract.py](../knowledge/extract.py)) and fed into the same
objective-parsing + source-retrieval pipeline as the `objectives` string. A deck
is just a richer way to supply `objectives`; slide titles/bullets become topic
signal, and the resulting deck is rebuilt from the engine's trusted sources, not
copied from the upload.

## Homework (prerequisite-aware coverage)
Supply a homework assignment (`homework` text and/or a `homeworkFile`) and the
deck prepares students to complete it — **without restating its questions,
solving any problem, or revealing answers.**

How it works in this deterministic engine: the homework text is mined for the
**concepts it exercises** (same taxonomy used for objectives). Concepts the
objectives don't already teach are added as extra **"Prerequisite Skills for the
Assignment"** sections — taught in full (concept slide + worked example/practice/
answer or illustration/review questions), but **kept off the title-slide agenda**.
The homework text itself is never rendered (it's only parsed to concepts), so the
no-leak guarantee holds by construction; retrieved examples that happen to echo
the homework wording are additionally dropped. Worked/practice problems come from
the engine's own curated/retrieved sources, so they are analogous to — never
copies of — the assignment's questions.

- Homework is fully optional and **additive** — absent ⇒ behavior is unchanged.
- It does **not** add agenda objectives; it only adds prerequisite coverage
  (capped at a handful of sections).
- Lenient: empty/over-cap homework is ignored/trimmed, not rejected. An
  unsupported `homeworkFile` type → `415`; an oversize one → `413`. If the
  homework yields no recognizable concepts, the deck is produced as if none was
  given.

## Supported file types
Extracted server-side: `.pptx`, `.docx`, `.xlsx`, `.pdf`, `.odt`, `.odp`, `.ods`,
`.rtf`, and plain-text/source files (`.txt`, `.md`, `.markdown`, `.rst`, `.csv`,
`.tsv`, `.json`, `.yaml`/`.yml`, and common code extensions: `.py`, `.js`, `.ts`,
`.jsx`, `.tsx`, `.java`, `.c`, `.h`, `.cpp`, `.cc`, `.cs`, `.go`, `.rb`, `.php`,
`.rs`, `.swift`, `.kt`, `.sql`, `.sh`, `.html`, `.css`, `.xml`).

**Not supported:** legacy binary `.doc` / `.ppt` / `.xls` (and anything else) →
`415`. Convert to a modern format or fall back to typed objectives.

## Size limit
The hosted deployment runs on Vercel, which caps the **request body at ~4.5 MB**;
larger uploads fail at the platform before reaching the function. Validate size
client-side. The server also returns `413` for oversize uploads (code-level cap
mirrors `/api/v1/materials`).

## Errors (standard envelope `{ "error": { "code", "message" } }`)

| Status | `code` | When |
|---|---|---|
| `400` | `invalid_request` | Neither `file` nor `objectives`; or merged objectives < 10 / > 4000 chars. |
| `401` | `unauthorized` | Auth required and key missing/invalid. |
| `413` | `payload_too_large` | File exceeds the size cap. |
| `415` | `unsupported_media_type` | File type not in the supported list. |
| `422` | `invalid_request` | File has no extractable text (empty/scanned) and no usable `objectives`. |

If a file yields *some* but thin text, the server proceeds (bounded by its
sources) rather than erroring — same as a short typed objectives string.

## Calling-app integration notes

- Switch to `FormData` when a file is present; keep the JSON path otherwise (mirror
  the existing materials uploader). **Do not** manually set `Content-Type` for
  `FormData` — the browser adds the multipart boundary.
- **Preserve the file extension** in the `FormData` filename — extraction
  dispatches on it (`fd.append("file", file, file.name)`).
- Send `X-API-Key` when the deployment is gated.
- Validate size (~4.5 MB) and extension client-side; surface `error.message` on 4xx.

```ts
const fd = new FormData();
fd.append("file", file, file.name);
if (objectives) fd.append("objectives", objectives);
if (title) fd.append("title", title);
const res = await fetch(`${BASE}/api/v1/lecture`, {
  method: "POST",
  headers: apiKey ? { "X-API-Key": apiKey } : {},   // no Content-Type
  body: fd,
});
if (!res.ok) throw new Error((await res.json())?.error?.message ?? `HTTP ${res.status}`);
const pptx = await res.blob();
```

## Backward compatibility
Purely additive — existing JSON `{ objectives, title }` callers are unaffected.
The only new behavior is the accepted `multipart/form-data` content type and the
`file` field.
