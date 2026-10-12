# Task 003 Report - RepoSage Android Retrieval Vertical Slice

## Summary

Implemented a minimal Android debug client under `android/` and stabilized the
Python API metadata response types for Android consumption. The Python retrieval
algorithm and ranking were not changed.

## Changed Files

- `backend/src/reposage/api.py`: added typed `IndexMetadataResponse` at the API
  boundary, converting stored metadata strings to booleans/integers/strings for
  responses.
- `backend/tests/test_api.py`: asserted API metadata types and retained CLI/API
  ordered chunk ID parity coverage.
- `backend/README.md`: documented stable API metadata types.
- `android/settings.gradle`, `android/build.gradle`, `android/app/build.gradle`:
  created a one-module Kotlin/Compose Android project.
- `android/app/src/main/AndroidManifest.xml`: declared internet permission and
  launcher activity.
- `android/app/src/debug/AndroidManifest.xml`,
  `android/app/src/debug/res/xml/debug_network_security_config.xml`: allowed
  local HTTP only in debug for `10.0.2.2`, `127.0.0.1`, and `localhost`.
- `android/app/src/main/java/com/reposage/app/MainActivity.kt`: wired Compose,
  the repository factory, and the ViewModel.
- `android/app/src/main/java/com/reposage/app/data/*`: added typed DTOs, domain
  models, Retrofit API interface, network repository, and repository factory.
- `android/app/src/main/java/com/reposage/app/ui/*`: added StateFlow ViewModel
  and a Compose search screen with initial, loading, results, empty, and retryable
  error states.
- `android/app/src/test/java/com/reposage/app/ui/SearchViewModelTest.kt`: added
  focused ViewModel tests for success, empty, error/retry, overlapping searches,
  and saved draft restoration.
- `android/app/src/test/java/com/reposage/app/data/SearchDtoParsingTest.kt`: added
  JSON parsing coverage for an actual `/search` response shape.
- `android/README.md`: documented setup, backend launch, emulator host access,
  adb reverse workflow, build, test, and install commands.
- Task 003B added the Android Gradle wrapper under `android/`, added
  `android/gradle.properties` for AndroidX, and captured genuine device
  screenshots under `outputs/`.

## API Contract

`POST /search` now returns stable metadata types:

- `git_dirty`: boolean
- `files_indexed`: integer
- `chunks_indexed`: integer
- `git_head`: string

Additional metadata fields are still available when present. Local checkout paths
and database paths are not exposed.

## Task 003B Environment And Build Unblock

No `AGENTS.md` file was present under the workspace slice inspected for this
task.

Project versions inspected:

- Android Gradle Plugin: `8.13.2`
- Kotlin Android/Compose/serialization plugins: `2.0.21`
- Gradle wrapper added for this Android slice: `8.14.3`
- Android app Java source/target compatibility: Java 17
- Android application ID: `com.reposage.app`

Installed JDKs inspected:

- System JDK: Java 12.0.2 at
  `/Library/Java/JavaVirtualMachines/jdk-12.0.2.jdk/Contents/Home`; too old for
  AGP 8.13.2.
- Android Studio JBR: Java 25.0.3; not compatible with this cached
  Gradle/Groovy runtime, which failed earlier with `Unsupported class file major
  version 69`.
- Selected build JDK: existing user-local Eclipse Temurin JDK 17.0.20.1 at
  `work/jdk17/Contents/Home` in the neighboring PocketAI workspace. No global
  Java defaults or Android Studio runtime were changed. The local source archive
  checksum recorded for that JDK artifact is
  `c01975da12ed4235250ff891fe8bba73a9e73037d444b269c9d0922b5dbc8e0a`.

Wrapper and local build configuration:

- Added a Gradle wrapper under `android/` because the Android slice did not have
  a checked-in wrapper script/properties/jar.
- Added `android/gradle.properties` with `android.useAndroidX=true`; the
  AndroidX dependency check otherwise failed before compilation.
- Added ignored local file `android/local.properties` with the Android SDK path
  for this machine only; no absolute SDK/JDK paths were added to tracked project
  configuration.

Wrapper checksums:

```text
63135287117a1e6d12c84580f1f49c61d1ba02218ecd28660605e97f976e7d65  android/gradlew
e996d452d2645e70c01c11143ca2d3742734a28da2bf61f25c82bdc288c9e637  android/gradle/wrapper/gradle-wrapper.jar
8f0bb0c9ccd5aa3ca33b2194296055f49d524aa9ac0e1d0eab7efdeabcc6d597  android/gradle/wrapper/gradle-wrapper.properties
```

`./gradlew --version` was run from `android/` with the selected JDK. Result:

```text
Gradle 8.14.3
Kotlin 2.0.21
Launcher JVM: 17.0.20.1 (Eclipse Adoptium 17.0.20.1+1)
Daemon JVM: work/jdk17/Contents/Home
OS: Mac OS X 12.7.6 x86_64
```

## Verification Performed

Backend tests:

```bash
work/task002-clean-venv/bin/python -m unittest discover -s backend/tests -v
```

Result: 8 tests passed. FastAPI emitted the existing Starlette/httpx deprecation
warning.

DevPulse evaluation:

```bash
work/task002-clean-venv/bin/reposage eval \
  --db .data/devpulse.db \
  --fixture backend/evaluation/devpulse_questions.json \
  --top-k 5
```

Result: 4/5 top-five hits, unchanged. The miss remains
`devpulse-toggle-saved`.

Real API curl:

```bash
REPOSAGE_DB_PATH=.data/devpulse.db \
  work/task002-clean-venv/bin/uvicorn reposage.api:app --host 127.0.0.1 --port 8000

curl -sS -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"How are GitHub HTTP errors mapped to DevPulse errors like rate limited, not found, and server error?","top_k":1}'
```

Result: 200 OK. The top result was:

```text
chunk_id: c554bbc23b3a13a918e17a14
path: core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt
lines: 1-42
citation: core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt:L1-L42
metadata: git_dirty=false, files_indexed=107, chunks_indexed=167,
          git_head=5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2
```

Excerpt from returned source:

```kotlin
internal fun Throwable.toDevPulseError(): DevPulseError =
    when (this) {
        is IOException -> DevPulseError.NetworkUnavailable
        is HttpException -> toHttpError()
        is SQLException -> DevPulseError.LocalStorageError(this)
        else -> DevPulseError.Unknown(this)
    }
```

Original Task 003 Android environment checks:

```bash
/usr/libexec/java_home -V
/Applications/Android\ Studio.app/Contents/jbr/Contents/Home/bin/java -version
/Users/batcomputer/Library/Android/sdk/platform-tools/adb devices
/Users/batcomputer/Library/Android/sdk/emulator/emulator -list-avds
```

Results:

- Installed system JDK: Java 12.0.2 only.
- Android Studio JBR: Java 25.0.3.
- Connected devices: none.
- Configured AVDs: none.

Android unit-test attempt:

```bash
JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk-12.0.2.jdk/Contents/Home \
  /Users/batcomputer/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle \
  testDebugUnitTest --no-daemon
```

Result: blocked before test execution because Android Gradle Plugin requires
Java 17 and the available system JDK is Java 12.

Android Studio JBR attempt:

```bash
JAVA_HOME='/Applications/Android Studio.app/Contents/jbr/Contents/Home' \
  /Users/batcomputer/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle \
  testDebugUnitTest --no-daemon
```

Result: blocked with `Unsupported class file major version 69`, so the Java 25
JBR is not usable for this Gradle/Groovy build here.

Android assemble attempt:

```bash
JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk-12.0.2.jdk/Contents/Home \
  /Users/batcomputer/.gradle/wrapper/dists/gradle-8.14.3-bin/cv11ve7ro1n3o1j4so8xd9n66/gradle-8.14.3/bin/gradle \
  assembleDebug --no-daemon
```

Result: blocked for the same Java 17 requirement.

Task 003B Android unit tests and debug build:

```bash
cd android
JAVA_HOME=<user-local-temurin-17> ./gradlew testDebugUnitTest assembleDebug
```

Result: `BUILD SUCCESSFUL in 3m 3s`.

The JVM unit test report contains 6 passing tests:

- `SearchViewModelTest`: 5 tests passed.
- `SearchDtoParsingTest`: 1 test passed.

The build emitted a non-fatal packaging warning for
`libandroidx.graphics.path.so` stripping, and a non-fatal Kotlin warning about a
redundant `Json` formatter in `SearchDtoParsingTest`.

Generated APK:

```text
android/app/build/outputs/apk/debug/app-debug.apk
size: 10,328,665 bytes
sha256: 560e992f9572289f272461af8ab7e6b5bd5b8920aceff17407aa729633c04aa8
```

The APK checksum above is from the physical-device build made with:

```bash
cd android
JAVA_HOME=<user-local-temurin-17> \
  ./gradlew assembleDebug -Preposage.backendUrl=http://127.0.0.1:8000/
```

That localhost override is required for the USB phone flow with `adb reverse`.

## Task 003B Device Validation

Connected device:

```text
204885a6  device
```

The device was awake and unlocked. The local backend was started against
`.data/devpulse.db`, `adb reverse tcp:8000 tcp:8000` returned `8000`, the APK
installed successfully with `adb install -r`, and `com.reposage.app/.MainActivity`
launched successfully.

Backend health returned:

```json
{
  "status": "ok",
  "index_ready": true,
  "index_metadata": {
    "git_dirty": false,
    "files_indexed": 107,
    "chunks_indexed": 167,
    "git_head": "5d6f5ebc842f6cf4bd8d6f2b716e08043ac695f2"
  }
}
```

Device checks:

- Real search: pass. Querying GitHub HTTP error mapping returned real indexed
  results from the backend.
- Exact code and citations: pass. The top result was
  `core/data/src/main/java/com/devpulse/core/data/error/ErrorMapping.kt:L1-L42`
  and the expanded snippet showed `IOException`, `HttpException`, HTTP 404,
  HTTP 429/rate-limit, and HTTP 500-599 server-error mapping code.
- Expanded snippets: pass. The result screen exposed `Expand code` and
  `Collapse code`, with source text present in the UI hierarchy.
- Empty results: pass. Query `zzznonexistenttermzzzxqj` displayed
  `No matching source chunks were found in the current index.` with index
  metadata.
- Backend-down error: pass. After stopping the local backend, a search displayed
  `Could not reach the RepoSage backend. Check the server connection and retry.`
  with a `Retry` action.
- Successful retry: pass. After restarting the backend and tapping `Retry`, the
  same query returned the empty-result success state rather than the connection
  error.
- Rotation draft preservation: pass. Draft text
  `rotation_draft_without_search` remained in the input after a portrait to
  landscape rotation and return to portrait.
- Rotation without duplicate requests: pass by observed backend logs. No new
  backend `POST /search` entries appeared while rotating the unsent draft.

Screenshots captured from the connected phone:

```text
outputs/android-result-expanded.png
sha256: 1b2b87446a53118f5bcf0b803b5bcaee8eddf55b4e68f65699a68a8d4ae4a422

outputs/android-error-backend-down.png
sha256: f8e8ffcae6c82dbdf8df012c7d4ebf77d8d1e545dde1cf0dd30f8aad0728ea8e
```

Rotation note: direct `settings put system ...` rotation changes were blocked by
Android `WRITE_SETTINGS`; validation used `cmd window user-rotation lock 1` and
restored `cmd window user-rotation free`.

## Pending Validation

- No remaining Task 003B build/unit/device validation is pending for the
  requested Android slice.
- Emulator validation remains unperformed because the physical OnePlus device
  was available and used for acceptance.

## Limitations

- The Android client is a debug vertical slice only.
- No generated answers, embeddings, authentication, saved history, or
  multi-repository support were added.
- The app assumes the backend is already running against a prebuilt index and no
  concurrent reindexing is happening.
- No emulator/AVD validation was performed because the physical phone was used
  for runtime acceptance.
