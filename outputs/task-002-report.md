# Task 002 Report

Implemented RepoSage's retrieval HTTP API on top of the existing Task 001
retrieval core. CLI behavior and ranking were left unchanged.

## Changed Files

- `backend/pyproject.toml`: declared FastAPI/uvicorn runtime dependencies,
  `httpx` test extra, and bumped version to `0.2.0`.
- `backend/src/reposage/api.py`: added FastAPI app with `GET /health` and
  `POST /search`.
- `backend/tests/test_api.py`: added API tests for success, exact citation/text,
  empty results, invalid input, unavailable index, and API/CLI ordered chunk ID
  parity.
- `backend/README.md`: documented setup, tests, indexing, API launch, curl, and
  Task 002 assumptions.

## Installation Reproducibility

Supported Python: 3.11 or newer. Verified with Python 3.12.13.

Clean venv command:

```bash
/Users/batcomputer/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv work/task002-clean-venv
work/task002-clean-venv/bin/python -m pip install -e 'backend[test]'
```

First attempt inside the restricted sandbox failed while downloading build
dependencies:

```text
Failed to establish a new connection: [Errno 8] nodename nor servname provided, or not known
ERROR: Could not find a version that satisfies the requirement setuptools>=68
```

After approved network access, clean installation succeeded and downloaded:
`fastapi-0.143.0`, `uvicorn-0.54.0`, `httpx-0.28.1`, and transitive
dependencies.

## Verification Commands Run

```bash
work/task002-clean-venv/bin/python -m unittest discover -s backend/tests -v

work/task002-clean-venv/bin/reposage eval --db .data/devpulse.db --fixture backend/evaluation/devpulse_questions.json --top-k 5

REPOSAGE_DB_PATH=.data/devpulse.db work/task002-clean-venv/bin/python -m uvicorn reposage.api:app --host 127.0.0.1 --port 8012

curl -sS -X POST http://127.0.0.1:8012/search -H 'Content-Type: application/json' -d '{"query":"How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?","top_k":1}'
```

The localhost server bind and curl needed elevated execution in this sandbox.
The first non-elevated server attempt failed with:

```text
error while attempting to bind on address ('127.0.0.1', 8012): [errno 1] operation not permitted
```

## Outcomes

- Tests: 8 passed.
- DevPulse evaluation: 4/5 top-five hits, unchanged from Task 001.
- API/CLI parity: automated test verifies the same ordered chunk IDs for the
  same query, `top_k`, and index.
- Health/search do not expose `repo_root`, `db_path`, or local checkout paths in
  responses.
- API assumes a prebuilt SQLite index and no concurrent reindexing.

## Real Curl Search

Request:

```bash
curl -sS -X POST http://127.0.0.1:8012/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?","top_k":1}'
```

Result summary:

- `query`: trimmed input query
- `index_metadata.git_head`: `5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2`
- top `chunk_id`: `c554bbc23b3a13a918e17a14`
- top citation: `core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt:L1-L42`
- `score`: `-38.37066020036226`

The response included repository-relative paths only and returned the exact
source chunk text for the cited line range.

## Remaining Blockers And Limits

- Dependency download requires network access. Without it, clean venv
  installation fails while resolving `setuptools>=68` before reaching FastAPI.
- The API has no auth, deployment hardening, generated answers, embeddings,
  indexing endpoint, or concurrent reindex coordination by design.
- The Task 001 retrieval limitation remains: `devpulse-toggle-saved` is still a
  top-five miss for the manually expected ViewModel/catalog code chunks.
