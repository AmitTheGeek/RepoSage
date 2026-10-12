"""RepoSage exception types."""


class RepoSageError(Exception):
    """Base class for actionable RepoSage errors."""


class RepositoryError(RepoSageError):
    """Raised when a repository path cannot be inspected safely."""


class Fts5UnavailableError(RepoSageError):
    """Raised when the active SQLite build lacks FTS5 support."""


class MissingIndexError(RepoSageError):
    """Raised when a database is missing or is not a RepoSage index."""


class BlankQueryError(RepoSageError):
    """Raised when a user query has no searchable terms."""
