# RepoSage Backend

RepoSage indexes a local Git checkout and retrieves source chunks with line citations.
The backend exposes the same retrieval core through both a CLI and a small
FastAPI application. It can optionally call Gemini from the server to produce
answers grounded in retrieved chunks. It does not use embeddings, clone remote
repositories, authenticate users, or serve Android UI.

## Setup

Use Python 3.11 or newer. Task 002 was verified with Python 3.12.13.

Run these commands from the repository root.

### 1. Create The Python Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e "backend[test]"
```

For runtime-only use, `python -m pip install -e backend` installs the CLI and API
dependencies. The `[test]` extra adds `httpx` for FastAPI test-client coverage.

If your Python's `sqlite3` module was not built with FTS5, `reposage index` exits
with an actionable error before writing the index.

### 2. Index A Local DevPulse Checkout

RepoSage indexes a local checkout that already exists on your machine. It does
not clone DevPulse for you.

```bash
reposage index \
  --repo /path/to/devpulse-checkout \
  --db .data/devpulse.db
```

The generated SQLite database is ignored by `.gitignore`.

### 3. Create A Gemini Key

Create a Gemini API key in Google AI Studio:

```text
https://aistudio.google.com/app/apikey
```

Do not enable billing for this project unless you explicitly intend to. RepoSage
defaults to `gemini-2.5-flash-lite`, which was selected because Google documents
it as available on the Gemini API free tier. Free-tier availability and quotas
are controlled by Google, so this is not a promise of unlimited usage.

### 4. Configure Backend Environment Variables

The Gemini key belongs only in the environment of the Python backend process. It
does not belong in Android code, README text, committed files, screenshots, or
Git history.

For macOS zsh/bash, prompt for the key without displaying it or saving the
literal key in shell history:

```bash
printf 'Gemini API key: '
IFS= read -r -s GEMINI_API_KEY
printf '\n'
export GEMINI_API_KEY
export REPOSAGE_GEMINI_MODEL='gemini-2.5-flash-lite'
export REPOSAGE_DB_PATH='.data/devpulse.db'
```

Presence-only check; this never prints the key:

```bash
if [ -n "${GEMINI_API_KEY:-}" ]; then
  echo "GEMINI_API_KEY is set"
else
  echo "GEMINI_API_KEY is missing"
fi
printf 'REPOSAGE_GEMINI_MODEL=%s\n' "$REPOSAGE_GEMINI_MODEL"
printf 'REPOSAGE_DB_PATH=%s\n' "$REPOSAGE_DB_PATH"
```

Start the backend from this same terminal so `uvicorn` inherits the variables.
A separately launched Codex session, IDE, or terminal tab will not automatically
inherit variables set here. If you close the terminal, configure the variables
again before restarting the backend. RepoSage does not automatically load `.env`
files.

Additional optional server-side controls:

- `REPOSAGE_GEMINI_TIMEOUT_MS`: request timeout in milliseconds, default `20000`.
- `REPOSAGE_GEMINI_MAX_OUTPUT_TOKENS`: structured answer output cap, default
  `1024`.

### 5. Start The Backend

From the same terminal where the virtual environment is active and the variables
above are set:

```bash
uvicorn reposage.api:app --host 127.0.0.1 --port 8000
```

The backend reads `REPOSAGE_DB_PATH`, `GEMINI_API_KEY`, and
`REPOSAGE_GEMINI_MODEL` from the Python process environment at runtime.

### 6. Test The API

Health:

```bash
curl -sS http://127.0.0.1:8000/health
```

Search:

```bash
curl -sS -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?","top_k":1}'
```

Answer:

```bash
curl -sS -X POST http://127.0.0.1:8000/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?","top_k":5}'
```

## Test

From the repository root:

```bash
python -m unittest discover -s backend/tests -v
```

The tests use temporary Git repositories only. They do not include or commit the
DevPulse corpus. Coverage includes retrieval behavior, HTTP API behavior, and
offline fake-provider coverage for structured Gemini answer orchestration.

## Index DevPulse

```bash
reposage index \
  --repo /path/to/devpulse-checkout \
  --db .data/devpulse.db
```

The indexer reads tracked files from Git, includes `.kt`, `.kts`, `.java`, `.xml`,
`.md`, and `.toml`, and skips unsupported extensions, generated/build output,
symlinks, non-UTF-8 content, credentials/local configuration, missing files, and
empty files. DevPulse code is never executed.

Generated databases are ignored by `.gitignore`.

## Search

```bash
reposage search \
  --db .data/devpulse.db \
  --query "How is search data cached?" \
  --top-k 5 \
  --json
```

Search accepts ordinary question text. The query is tokenized into safe FTS terms,
so user input is not interpreted as raw SQL or unrestricted FTS syntax. Scores are
adjusted SQLite FTS5 BM25 ranking values: lower ranks higher, and scores are not
confidence values.

Each result includes:

- `chunk_id`
- `path`
- `start_line`
- `end_line`
- `text`
- `score`
- `citation`, formatted as `relative/path/File.kt:L10-L35`

## HTTP API

Task 002 assumes a prebuilt index. Keep indexing as a separate CLI operation and
do not reindex concurrently with API requests.

Configure the index server-side with `REPOSAGE_DB_PATH`; clients cannot provide
filesystem paths or SQL.

Optional Gemini answering is also configured server-side with `GEMINI_API_KEY`
and `REPOSAGE_GEMINI_MODEL`, as shown in the setup steps above.

`POST /search` accepts:

```json
{"query": "...", "top_k": 5}
```

Behavior:

- `query` is trimmed, must not be blank, and is limited to 2,000 characters.
- `top_k` defaults to 5 and must be an integer from 1 to 20.
- Invalid requests return 422.
- No matches return 200 with an empty `results` list.
- Missing or unusable indexes return 503 with a safe setup message.
- Health reports index readiness without exposing local checkout or database
  paths.
- Search responses include safe index metadata, score direction, and repository
  relative result paths only.
- `/answer` uses the same request validation and retrieval path as `/search`.
- If retrieval returns no chunks, `/answer` returns `insufficient_evidence`
  without calling Gemini.
- Retrieved chunks are assigned request-local source IDs such as `S1` and `S2`.
  Only chunks sent to Gemini may be cited.
- The answer evidence context is capped at 20,000 formatted characters. Chunks
  are deduplicated, and over-budget chunks are omitted whole rather than
  truncated.
- Gemini must return structured JSON containing `status` and `claims`. The
  server validates that every answered claim cites supplied source IDs, then
  resolves paths, line ranges, and citation strings from stored retrieval
  metadata. It never trusts model-generated paths or line numbers.
- Citation/reference validation is structural; it does not prove semantic
  correctness of a generated claim.

`POST /answer` error codes:

- `503 gemini_not_configured`: Gemini SDK/key configuration is missing.
- `429 gemini_quota_or_rate_limited`: Gemini returned a quota or rate-limit
  failure.
- `504 gemini_timeout`: Gemini did not respond within the configured timeout.
- `502 gemini_provider_failure`: Gemini failed for another provider-side reason.
- `502 gemini_invalid_response`: Gemini returned malformed output or cited an
  unknown source ID.

`index_metadata` response types are stable at the API boundary:

- `git_dirty`: boolean
- `files_indexed`: integer
- `chunks_indexed`: integer
- `git_head`: string

Additional metadata fields such as `schema_version`, `indexed_at_utc`,
`chunk_lines`, and `overlap_lines` may also be present.

## Troubleshooting

- Missing key: if `/answer` has retrieved evidence but `GEMINI_API_KEY` is not
  set in the backend process, it returns `503` with
  `gemini_not_configured`. Configure the key in the same terminal that starts
  `uvicorn`.
- Invalid key: Gemini authentication failures are provider-side failures in the
  current adapter and return `502` with `gemini_provider_failure`.
- Unavailable model: an invalid or unavailable `REPOSAGE_GEMINI_MODEL` also
  returns `502` with `gemini_provider_failure`.
- Quota or rate limit exhausted: Gemini quota/rate-limit responses return `429`
  with `gemini_quota_or_rate_limited`. RepoSage does not automatically switch to
  another model.
- Missing index: `/health` reports `index_ready: false`, while `/search` and
  `/answer` return `503` with the safe index setup message. Build the index and
  set `REPOSAGE_DB_PATH` in the backend process environment.
- No matching chunks: `/search` returns an empty `results` list. `/answer`
  returns `insufficient_evidence` without calling Gemini.

## Evaluate

The fixed DevPulse evaluation fixture is:

```text
backend/evaluation/devpulse_questions.json
```

Run:

```bash
reposage eval \
  --db .data/devpulse.db \
  --fixture backend/evaluation/devpulse_questions.json \
  --top-k 5
```

Task 001 evaluation run:

- DevPulse checkout: local DevPulse working tree; absolute machine path omitted
- Git HEAD: `5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2`
- Dirty state: `false`
- Files indexed: 107
- Chunks indexed: 167
- Chunking: 80 lines with 15-line overlap
- Result: 4/5 fixed questions retrieved a manually identified supporting code chunk in the top five

| Question id | Result |
| --- | --- |
| `devpulse-cache-freshness` | hit |
| `devpulse-owner-list-snapshot` | hit |
| `devpulse-toggle-saved` | miss |
| `devpulse-error-mapping` | hit |
| `devpulse-search-validation` | hit |

Known limitation from this run: the save/unsave question retrieved relevant UI and
test chunks, but the manually expected `RepositoryViewModel` and
`DefaultRepositoryCatalog` chunks ranked outside the top five.

Task 002 regression run:

- Unit/API tests: 8 passed.
- DevPulse evaluation: unchanged at 4/5 top-five hits.
- CLI/API ordered chunk IDs were verified equal in automated tests for the same
  query, `top_k`, and index.

## Design Notes

- Full rebuilds drop and recreate the RepoSage tables, so deleted files and old
  chunks do not remain in the index.
- Searchable text expands camelCase and snake_case identifiers while preserving
  exact original source text separately for citations.
- Markdown is indexed, but receives a ranking penalty so source code is favored
  for code-oriented questions.
- Citations refer to the indexed working-tree snapshot, including dirty state.
- The API opens SQLite connections per request through the retrieval core; it
  does not keep a shared writable connection.
