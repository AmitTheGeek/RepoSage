"""Read tracked source files from a local Git checkout without executing it."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from reposage.errors import RepositoryError
from reposage.models import IngestedFile, SkippedFile

ALLOWED_EXTENSIONS = {".kt", ".kts", ".java", ".xml", ".md", ".toml"}
GENERATED_PARTS = {".git", ".gradle", "build", "out", "generated"}
LOCAL_CONFIG_NAMES = {
    ".env",
    ".env.local",
    "local.properties",
    "gradle.properties.local",
}
SENSITIVE_NAME_PARTS = {
    "credential",
    "credentials",
    "keystore",
    "secret",
    "secrets",
}


@dataclass(frozen=True)
class GitMetadata:
    head: str | None
    dirty: bool


@dataclass(frozen=True)
class IngestionResult:
    repo_root: Path
    git_metadata: GitMetadata
    files: list[IngestedFile]
    skipped_files: list[SkippedFile]


def ingest_repository(repo_path: str | Path) -> IngestionResult:
    repo_root = resolve_git_root(repo_path)
    git_metadata = read_git_metadata(repo_root)
    tracked_paths = _tracked_paths(repo_root)

    files: list[IngestedFile] = []
    skipped: list[SkippedFile] = []

    for relative_path in tracked_paths:
        reason = _skip_reason(relative_path)
        if reason is not None:
            skipped.append(SkippedFile(relative_path, reason))
            continue

        absolute_path = repo_root / relative_path
        if not absolute_path.exists():
            skipped.append(SkippedFile(relative_path, "missing from working tree"))
            continue
        if absolute_path.is_symlink():
            skipped.append(SkippedFile(relative_path, "symlink"))
            continue
        if not absolute_path.is_file():
            skipped.append(SkippedFile(relative_path, "not a regular file"))
            continue

        try:
            raw = absolute_path.read_bytes()
        except OSError as exc:
            skipped.append(SkippedFile(relative_path, f"unreadable: {exc}"))
            continue

        if b"\x00" in raw:
            skipped.append(SkippedFile(relative_path, "binary content"))
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(SkippedFile(relative_path, "not UTF-8"))
            continue

        if text == "":
            skipped.append(SkippedFile(relative_path, "empty file"))
            continue

        files.append(
            IngestedFile(
                path=relative_path,
                absolute_path=absolute_path,
                text=text,
                content_hash=hashlib.sha256(raw).hexdigest(),
                line_count=len(text.splitlines()),
            ),
        )

    return IngestionResult(
        repo_root=repo_root,
        git_metadata=git_metadata,
        files=files,
        skipped_files=skipped,
    )


def resolve_git_root(repo_path: str | Path) -> Path:
    path = Path(repo_path).expanduser().resolve()
    if not path.exists():
        raise RepositoryError(f"repository path does not exist: {path}")
    if not path.is_dir():
        raise RepositoryError(f"repository path is not a directory: {path}")

    result = _git(path, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or "not a Git checkout"
        raise RepositoryError(f"{path} is not a Git checkout: {detail}")
    return Path(result.stdout.strip()).resolve()


def read_git_metadata(repo_root: Path) -> GitMetadata:
    head_result = _git(repo_root, "rev-parse", "HEAD", check=False)
    head = head_result.stdout.strip() if head_result.returncode == 0 else None
    status_result = _git(repo_root, "status", "--porcelain", check=True)
    return GitMetadata(head=head, dirty=bool(status_result.stdout.strip()))


def _tracked_paths(repo_root: Path) -> list[str]:
    result = _git(repo_root, "ls-files", "-z", check=True)
    return sorted(path for path in result.stdout.split("\0") if path)


def _skip_reason(relative_path: str) -> str | None:
    path = Path(relative_path)
    parts = {part.lower() for part in path.parts}
    filename = path.name.lower()
    stem = path.stem.lower()

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return "unsupported extension"
    if parts & GENERATED_PARTS:
        return "generated/build output"
    if filename in LOCAL_CONFIG_NAMES:
        return "credentials/local configuration"
    if any(secret in stem for secret in SENSITIVE_NAME_PARTS):
        return "credentials/local configuration"
    return None


def _git(
    repo_root: Path,
    *args: str,
    check: bool,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RepositoryError(f"git {' '.join(args)} failed: {detail}")
    return result
