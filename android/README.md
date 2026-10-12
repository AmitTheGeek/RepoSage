# RepoSage Android

Minimal debug Android client for the RepoSage retrieval API. The app submits a
question to an existing Python `/search` endpoint and renders returned source
chunks with citations. It does not index repositories or change retrieval
ranking.

## Requirements

- Android SDK with platform 36 installed.
- JDK 17 or 21. Java 12 is too old for Android Gradle Plugin 8.13.2, and the
  Java 25 JBR bundled with the local Android Studio install is not usable with
  the cached Gradle/Groovy runtime in this workspace.
- Gradle 8.13 or newer.

## Backend

Task 003 assumes a prebuilt RepoSage index. From the repository root:

```bash
source .venv/bin/activate
REPOSAGE_DB_PATH=.data/devpulse.db \
  uvicorn reposage.api:app --host 127.0.0.1 --port 8000
```

For an Android emulator, the debug app defaults to:

```text
http://10.0.2.2:8000/
```

For a USB-connected physical phone, reverse the port and build with the localhost
override:

```bash
adb reverse tcp:8000 tcp:8000
cd android
gradle :app:assembleDebug -Preposage.backendUrl=http://127.0.0.1:8000/
```

Local cleartext HTTP is allowed only by the debug manifest network-security
configuration.

## Build And Test

From `android/` with `JAVA_HOME` pointing to JDK 17 or 21:

```bash
gradle testDebugUnitTest
gradle assembleDebug
```

Focused tests cover ViewModel success, empty results, retry after errors,
overlapping searches, draft restoration, and JSON parsing for the actual API
response structure.

## Install

With a device or emulator available:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Then start the backend, open RepoSage, enter a question, and expand a result to
inspect the exact retrieved source text and citation.
