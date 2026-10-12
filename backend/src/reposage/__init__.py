"""RepoSage local repository retrieval core."""

from reposage.indexing import index_repository
from reposage.retrieval import search

__all__ = ["index_repository", "search"]
