# RepoSage Android

Minimal debug Android client for the RepoSage retrieval API. The app submits a
question to an existing Python backend and lets you choose:

- `Ask`: call `POST /answer` and render answer claims with source references.
- `Search code`: call `POST /search` and render retrieved source chunks with
  citations.

It does not index repositories, change retrieval ranking, configure Gemini, or
fabricate answers when the backend is unavailable.

## Requirements

- Android SDK with platform 36 installed.
- JDK 17 or 21. Java 12 is too old for Android Gradle Plugin 8.13.2, and the
  Java 25 JBR bundled with the local Android Studio install is not usable with
  the cached Gradle/Groovy runtime in this workspace.
- The checked-in Gradle wrapper under `android/`.

## Backend

Task 003 assumes a prebuilt RepoSage index. From the repository root:

```bash
source .venv/bin/activate
REPOSAGE_DB_PATH=.data/devpulse.db \
  uvicorn reposage.api:app --host 127.0.0.1 --port 8000
```

`Ask` requires the backend `/answer` endpoint to be configured server-side with
`GEMINI_API_KEY` and `REPOSAGE_GEMINI_MODEL`. The Android app never stores or
sends a Gemini key directly.

For an Android emulator, the debug app defaults to:

```text
http://10.0.2.2:8000/
```

For a USB-connected physical phone, reverse the port and build with the localhost
override:

```bash
adb reverse tcp:8000 tcp:8000
cd android
./gradlew :app:assembleDebug -Preposage.backendUrl=http://127.0.0.1:8000/
```

Local cleartext HTTP is allowed only by the debug manifest network-security
configuration.

## Build And Test

From `android/` with `JAVA_HOME` pointing to JDK 17 or 21:

```bash
./gradlew testDebugUnitTest
./gradlew assembleDebug
./gradlew assembleDebugAndroidTest
```

Focused tests cover ViewModel success, empty results, retry after errors,
overlapping requests, draft restoration, answer/abstention states, retrying the
submitted question snapshot, JSON parsing for the actual `/search` and `/answer`
response structures, and compilation of mock-server Compose UI tests.

Run connected mock UI tests only when a device or emulator is available:

```bash
./gradlew connectedDebugAndroidTest
```

The connected tests use deterministic `MockWebServer` responses and do not call
Gemini.

## Install

With a device or emulator available:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Then start the backend, open RepoSage, enter a question, choose `Ask` or
`Search code`, and inspect the returned answer references or retrieved source
text. Live Gemini answer quality is still pending manual acceptance.
