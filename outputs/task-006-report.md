# Task 006 Report - Reproducible Offline CI

## Summary

Added a GitHub Actions workflow for self-contained RepoSage checks that do not
require Gemini credentials or a local DevPulse checkout.

The workflow has two independent jobs:

- `backend`: install the Python package with test dependencies, confirm SQLite
  FTS5 support, and run the offline backend unit/API tests.
- `android`: set up JDK 17, install Android SDK platform/build-tools 36, run
  JVM unit tests, assemble the debug APK, and assemble the Android test APK.

Android test reports and the debug APK are uploaded as short-retention workflow
artifacts. Live Gemini answer evaluation, local DevPulse retrieval evaluation,
connected Android UI tests, and manual device acceptance remain outside CI.

## Workflow Configuration

- Triggers: pushes to `main` and pull requests targeting `main`.
- Permissions: `contents: read`.
- Concurrency: superseded runs for the same workflow/ref are cancelled.
- Action versions selected from current official action documentation:
  `actions/checkout@v7`, `actions/setup-python@v7`,
  `actions/setup-java@v6`, and `actions/upload-artifact@v7`.

## Equivalent Local Commands

Backend:

```bash
python -m pip install -e "backend[test]"
python - <<'PY'
import sqlite3
connection = sqlite3.connect(":memory:")
connection.execute("CREATE VIRTUAL TABLE probe USING fts5(value)")
print("SQLite FTS5 available")
PY
python -m unittest discover -s backend/tests -v
```

Android:

```bash
cd android
./gradlew --no-daemon testDebugUnitTest
./gradlew --no-daemon assembleDebug
./gradlew --no-daemon assembleDebugAndroidTest
```

## Local Verification

Workflow syntax was parsed locally with Ruby's YAML parser:

```bash
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/ci.yml")'
```

Result:

```text
workflow YAML parsed
```

Backend verification used the existing Python 3.12.13 virtual environment:

```bash
work/task002-clean-venv/bin/python -m pip install -e "backend[test]"
work/task002-clean-venv/bin/python - <<'PY'
import sqlite3
connection = sqlite3.connect(":memory:")
connection.execute("CREATE VIRTUAL TABLE reposage_fts5_probe USING fts5(value)")
connection.execute("INSERT INTO reposage_fts5_probe(value) VALUES (?)", ("probe",))
rows = list(connection.execute(
    "SELECT value FROM reposage_fts5_probe WHERE reposage_fts5_probe MATCH 'probe'"
))
assert rows == [("probe",)]
print("SQLite FTS5 available")
PY
work/task002-clean-venv/bin/python -m unittest discover -s backend/tests -v
```

Results:

```text
Editable install: passed
SQLite FTS5 available
Ran 17 tests in 5.699s
OK
```

Android verification used Temurin JDK 17.0.20.1:

```bash
cd android
JAVA_HOME=/path/to/jdk17 \
  ./gradlew --no-daemon testDebugUnitTest
JAVA_HOME=/path/to/jdk17 \
  ./gradlew --no-daemon assembleDebug
JAVA_HOME=/path/to/jdk17 \
  ./gradlew --no-daemon assembleDebugAndroidTest
```

Results:

```text
testDebugUnitTest: BUILD SUCCESSFUL in 1m 34s
assembleDebug: BUILD SUCCESSFUL in 1m 10s
assembleDebugAndroidTest: BUILD SUCCESSFUL in 1m
```

The first local backend install attempt was blocked by sandboxed network access
while fetching isolated build dependencies; rerunning the same install with
network access succeeded. The first Android command also needed unsandboxed
execution because the Gradle wrapper writes through the user-level
`~/.gradle/wrapper` cache.

Pending:

- Hosted GitHub Actions execution after push.
- Connected Android UI tests, because those require a device or emulator.
- Live Gemini answer-quality evaluation, because that requires server-side
  Gemini credentials/quota and source review.
