# Task 001 Report

Implemented RepoSage's local retrieval core and CLI under `backend/`.

## Evaluated DevPulse Checkout

- Path: local DevPulse working tree; absolute machine path omitted
- Git HEAD: `5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2`
- Dirty state: `false`

## Verification Commands Run

```bash
python -m unittest discover -s backend/tests -v

PYTHONPATH=backend/src python -m reposage.cli index --repo /path/to/devpulse-checkout --db .data/devpulse.db --json

PYTHONPATH=backend/src python -m reposage.cli eval --db .data/devpulse.db --fixture backend/evaluation/devpulse_questions.json --top-k 5

work/reprosage-venv-system/bin/python -m pip install --no-build-isolation -e backend

work/reprosage-venv-system/bin/reposage search --db .data/devpulse.db --query "How is search data cached?" --top-k 5 --json
```

Note: an initial editable-install attempt in a fully isolated venv failed because
that venv did not include `setuptools`; the system-site-packages venv install
above succeeded without downloading dependencies.

## Results

- Unit tests: 3 tests passed.
- Indexing: 107 files, 167 chunks, 14 skipped tracked files reported.
- Evaluation: 4/5 top-five hits.

| Question id | Result |
| --- | --- |
| `devpulse-cache-freshness` | hit |
| `devpulse-owner-list-snapshot` | hit |
| `devpulse-toggle-saved` | miss |
| `devpulse-error-mapping` | hit |
| `devpulse-search-validation` | hit |

The remaining miss retrieved relevant UI/test chunks, but not the manually
expected `RepositoryViewModel` or `DefaultRepositoryCatalog` chunks in the top
five.

## Real Query Verification

Query:

```text
How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?
```

Top result:

```text
core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt:L1-L42
```

The retrieved text was compared with the cited DevPulse working-tree line range
and matched exactly.
