# Task 005 Report - Android Answer Flow With Mock Verification

## Summary

Connected the Android debug app to the existing backend `POST /answer` contract
without changing backend Gemini configuration, retrieval ranking, or live
answer-quality status.

The app now offers two explicit actions:

- `Ask`: calls `/answer` and displays answer claims with source references.
- `Search code`: preserves the existing `/search` source-retrieval flow.

No live Gemini calls were made in this task.

## Implementation

- Added typed Android DTO/domain models for the actual `/answer` response:
  `query`, `status`, `model_id`, `index_metadata`, `score_direction`, `claims`,
  `sources`, optional `usage`, and optional `latency_ms`.
- Added Retrofit support for `POST /answer` using the same `{query, top_k}`
  request shape as `/search`.
- Mapped backend answer error codes into recoverable Android messages:
  - `gemini_not_configured`
  - `gemini_quota_or_rate_limited`
  - `gemini_timeout`
  - `gemini_provider_failure`
  - `gemini_invalid_response`
- Preserved `/search` behavior and its existing empty/error states.
- Updated the ViewModel so each request captures an immutable submitted
  question and mode. Retry uses that snapshot, not the edited draft.
- Reused request IDs and coroutine cancellation so older answer/search requests
  cannot overwrite newer results.
- Kept cancellation from surfacing as an error by rethrowing coroutine
  cancellation from the repository.
- Added answer UI for:
  - loading while answer generation is in progress
  - answer claims
  - tappable source IDs such as `S1`
  - opened source path, line range, citation, and exact source text
  - compact model/revision details
  - explicit insufficient-evidence state

Insufficient evidence is presented as an abstention from supplied evidence, not
as proof that a feature is absent.

## Tests Added

JVM unit tests now cover:

- `/answer` response parsing.
- insufficient-evidence response parsing.
- backend answer error-code parsing.
- successful answer state with claim/source association.
- insufficient-evidence state.
- retry using the submitted answer snapshot.
- stale answer response not overwriting a newer search request.
- existing search success, empty, retry, stale-response, and draft restoration
  coverage.

Connected Compose tests were added under `androidTest` using deterministic
`MockWebServer` responses for:

- opening a cited answer source.
- displaying insufficient evidence.
- preserving the existing `Search code` flow.

These connected tests compile, but were not executed because no device or AVD was
available.

## Verification

Commands were run with Temurin JDK 17.0.20.1:

```bash
cd android
JAVA_HOME=/path/to/jdk17 \
  ./gradlew testDebugUnitTest
```

Result:

```text
BUILD SUCCESSFUL in 7s
31 actionable tasks: 2 executed, 29 up-to-date
```

Unit test report:

```text
SearchDtoParsingTest: 4 tests, 0 failures
SearchViewModelTest: 9 tests, 0 failures
```

```bash
cd android
JAVA_HOME=/path/to/jdk17 \
  ./gradlew assembleDebug
```

Result:

```text
BUILD SUCCESSFUL in 18s
39 actionable tasks: 5 executed, 34 up-to-date
```

```bash
cd android
JAVA_HOME=/path/to/jdk17 \
  ./gradlew assembleDebugAndroidTest
```

Result:

```text
BUILD SUCCESSFUL in 2s
52 actionable tasks: 52 up-to-date
```

Generated debug APK:

```text
android/app/build/outputs/apk/debug/app-debug.apk
size: 10,371,237 bytes
sha256: e99af16bbc81f07c53ee865de59b1fc4bee98e3d78b6cdab376dd702a1fde8c2
```

Device/emulator availability:

```text
adb devices -> no devices attached
emulator -list-avds -> no configured AVDs
```

`connectedDebugAndroidTest` was not run.

## Pending Checks

- Run `./gradlew connectedDebugAndroidTest` on a connected device or emulator to
  execute the mock-server Compose UI tests.
- Capture mock-data screenshots only if needed, and label them as mock evidence.
- Run live `/answer` quality evaluation after backend Gemini model/key access is
  resolved. Task 004 answer-quality acceptance remains pending.
- Review live answers against cited source text before making any live RAG
  acceptance claim.

## Notes

- No API keys were added to Android code or documentation.
- No backend Gemini defaults, billing settings, retrieval ranking, or server-side
  prompt behavior were changed.
- The app never falls back to fabricated answers in normal runtime behavior.
