# Task 004 Report - Gemini Answers Grounded In Retrieved Code

## Summary

Added a backend-only `/answer` endpoint that retrieves RepoSage chunks, builds a
bounded evidence context with request-local source IDs, asks Gemini for
structured output, and validates returned source references before resolving
citations from stored metadata.

Android was not changed.

## Documentation Checked

Official Gemini documentation checked on 2026-10-13:

- Google Gen AI Python SDK docs for `google-genai`, `GEMINI_API_KEY`, client
  construction, structured JSON/Pydantic output, client cleanup, and HTTP
  timeout support.
- Gemini API pricing docs for a free-tier-eligible model. RepoSage defaults to
  `gemini-2.5-flash-lite`, with `REPOSAGE_GEMINI_MODEL` available as a
  server-side override.

## Implementation

- `POST /answer` accepts the same `query` and `top_k` shape as `/search` and
  reuses existing search validation and retrieval.
- `/search` behavior is preserved.
- Evidence sources are assigned request-local IDs such as `S1` and `S2`.
- Duplicate chunks are removed before prompting.
- The evidence context is capped at 20,000 formatted characters. Over-budget
  chunks are omitted whole; source text is not silently truncated.
- Only sources included in the evidence context may be cited.
- The Gemini adapter is behind an injectable provider interface.
- Gemini is configured server-side through `GEMINI_API_KEY` and
  `REPOSAGE_GEMINI_MODEL`.
- The adapter requests structured JSON with:
  - `status`: `answered` or `insufficient_evidence`
  - `claims`: claim text plus supporting source IDs
- The server validates status, claim shape, non-empty claim text, and all source
  IDs.
- Paths, line ranges, citations, and source text in API responses come from
  RepoSage retrieval metadata, never model-generated values.
- Citation validation is structural and does not prove semantic correctness.
- No tools, browsing, code execution, or agent framework are used.

## Error Handling

Documented safe API errors:

- `503 gemini_not_configured`
- `429 gemini_quota_or_rate_limited`
- `504 gemini_timeout`
- `502 gemini_provider_failure`
- `502 gemini_invalid_response`

The implementation does not log credentials or full prompts by default and sets
a bounded Gemini timeout/output limit. Automatic retry loops are disabled through
the Gemini SDK HTTP retry options.

## Dependency Note

Added `google-genai>=1.0,<2`.

The first dependency install attempted `cryptography 50.0.2` from source and
failed because OpenSSL development metadata was unavailable to `pkg-config`.
Adding `cryptography<46` selected the prebuilt `cryptography 45.0.7` wheel and
allowed the backend dependency install to complete without changing system
OpenSSL or global Python configuration.

Validated installed package:

```text
google-genai 1.75.0
```

## Offline Verification

Command:

```bash
work/task002-clean-venv/bin/python -m unittest discover -s backend/tests -v
```

Result:

```text
Ran 17 tests in 3.279s
OK
```

Coverage added:

- Supported claims resolve to stored citations/source text.
- Gemini abstention is allowed even when retrieval returns matches.
- No-match `/answer` returns `insufficient_evidence` without constructing or
  calling a provider.
- Unknown source IDs are rejected with a safe `gemini_invalid_response`.
- Malformed provider output is rejected.
- Timeout maps to `gemini_timeout`.
- Quota/rate-limit maps to `gemini_quota_or_rate_limited`.
- Missing Gemini configuration maps to `gemini_not_configured`.
- Context budgeting deduplicates chunks and omits whole over-budget chunks.

Existing retrieval/API tests still pass.

## Retrieval Evaluation

Command:

```bash
work/task002-clean-venv/bin/reposage eval \
  --db .data/devpulse.db \
  --fixture backend/evaluation/devpulse_questions.json \
  --top-k 5
```

Result:

```text
Hits: 4/5 at top 5
```

Per-question status:

- `devpulse-cache-freshness`: hit
- `devpulse-owner-list-snapshot`: hit
- `devpulse-toggle-saved`: miss
- `devpulse-error-mapping`: hit
- `devpulse-search-validation`: hit

The known save/unsave retrieval miss remains visible. Ranking was not tuned in
this task.

## Live Gemini Evaluation

Blocked.

Environment check:

```text
GEMINI_API_KEY_MISSING
REPOSAGE_GEMINI_MODEL_MISSING
```

Because no Gemini API key was configured, no live `/answer` calls were made and
no answer quality acceptance is claimed.

Planned live set, still pending:

- The five existing DevPulse evaluation questions.
- Absent-evidence question: "What OAuth scopes does DevPulse request for GitHub
  login?"
- Absent-evidence question: "How does DevPulse encrypt saved repository data at
  rest?"

For live acceptance, each answer should be reviewed manually against cited
source text and categorized as supported claim, retrieval miss, unsupported
claim, correct abstention, or incorrect abstention. Model ID, date, latency, and
usage should be recorded when returned by Gemini.

## Limitations

- Live answer quality is unverified until credentials/quota are available.
- Source-reference validation checks that source IDs were supplied and resolves
  citations from stored metadata; it does not prove claim semantics.
- The Android app still uses retrieval only and does not call `/answer`.
- The backend assumes a prebuilt SQLite index and no concurrent reindexing.
- The known 4/5 retrieval fixture result remains unchanged.
