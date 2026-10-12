# RepoSage Backend

RepoSage indexes a local Git checkout and retrieves source chunks with line citations.
The backend exposes the same retrieval core through both a CLI and a small
FastAPI application. It does not call LLMs, use embeddings, clone remote
repositories, authenticate users, or serve Android UI.

## Setup

Use Python 3.11 or newer. Task 002 was verified with Python 3.12.13.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e "backend[test]"
```

For runtime-only use, `python -m pip install -e backend` installs the CLI and API
dependencies. The `[test]` extra adds `httpx` for FastAPI test-client coverage.

If your Python's `sqlite3` module was not built with FTS5, `reposage index` exits
with an actionable error before writing the index.

## Test

From the repository root:

```bash
python -m unittest discover -s backend/tests -v
```

The tests use temporary Git repositories only. They do not include or commit the
DevPulse corpus. Coverage includes Task 001 retrieval behavior and Task 002 HTTP
API behavior.

## Index DevPulse

```bash
reposage index \
  --repo /Users/batcomputer/Documents/Codex/2026-09-08/we-are-starting-a-production-quality \
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

Launch the development server on localhost:

```bash
REPOSAGE_DB_PATH=.data/devpulse.db \
  uvicorn reposage.api:app --host 127.0.0.1 --port 8000
```

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

`index_metadata` response types are stable at the API boundary:

- `git_dirty`: boolean
- `files_indexed`: integer
- `chunks_indexed`: integer
- `git_head`: string

Additional metadata fields such as `schema_version`, `indexed_at_utc`,
`chunk_lines`, and `overlap_lines` may also be present.

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

- DevPulse checkout: `/Users/batcomputer/Documents/Codex/2026-09-08/we-are-starting-a-production-quality`
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
