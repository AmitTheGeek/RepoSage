"""Command-line interface for RepoSage."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from reposage.errors import RepoSageError
from reposage.evaluation import evaluate
from reposage.indexing import index_repository
from reposage.retrieval import search
from reposage.storage import SCORE_DIRECTION, read_metadata


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "index":
            return _index_command(args)
        if args.command == "search":
            return _search_command(args)
        if args.command == "eval":
            return _eval_command(args)
    except RepoSageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    parser.error("unknown command")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reposage")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="index a local Git checkout")
    index_parser.add_argument("--repo", required=True, help="path to local checkout")
    index_parser.add_argument("--db", required=True, help="SQLite database path")
    index_parser.add_argument("--chunk-lines", type=int, default=80)
    index_parser.add_argument("--overlap", type=int, default=15)
    index_parser.add_argument("--json", action="store_true")

    search_parser = subparsers.add_parser("search", help="search an existing index")
    search_parser.add_argument("--db", required=True, help="SQLite database path")
    search_parser.add_argument("--query", required=True, help="ordinary question text")
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--json", action="store_true")

    eval_parser = subparsers.add_parser("eval", help="evaluate fixed questions")
    eval_parser.add_argument("--db", required=True, help="SQLite database path")
    eval_parser.add_argument("--fixture", required=True, help="evaluation fixture JSON")
    eval_parser.add_argument("--top-k", type=int, default=5)
    eval_parser.add_argument("--json", action="store_true")

    return parser


def _index_command(args: argparse.Namespace) -> int:
    report = index_repository(
        args.repo,
        args.db,
        chunk_lines=args.chunk_lines,
        overlap_lines=args.overlap,
    )
    payload = _index_report_payload(report)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Indexed {report.files_indexed} files into {report.chunks_indexed} chunks.")
        print(f"Database: {report.db_path}")
        print(f"Git HEAD: {report.git_head or '(none)'}")
        print(f"Dirty state: {str(report.git_dirty).lower()}")
        if report.skipped_files:
            print("Skipped files:")
            for skipped in report.skipped_files:
                print(f"- {skipped.path}: {skipped.reason}")
    return 0


def _search_command(args: argparse.Namespace) -> int:
    results = search(args.db, args.query, top_k=args.top_k)
    payload = {
        "query": args.query,
        "top_k": args.top_k,
        "score_direction": SCORE_DIRECTION,
        "results": [asdict(result) for result in results],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Score direction: {SCORE_DIRECTION}.")
        if not results:
            print("No matches.")
        for index, result in enumerate(results, start=1):
            print(f"{index}. {result.citation} score={result.score}")
            print(result.text)
    return 0


def _eval_command(args: argparse.Namespace) -> int:
    metadata = read_metadata(args.db)
    payload = evaluate(args.db, args.fixture, top_k=args.top_k)
    payload["index_metadata"] = metadata
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Hits: {payload['hits']}/{payload['total']} at top {args.top_k}")
        print(f"Git HEAD: {metadata.get('git_head') or '(none)'}")
        print(f"Dirty state: {metadata.get('git_dirty', 'unknown')}")
        for question in payload["questions"]:
            status = "hit" if question["hit"] else "miss"
            print(f"- {question['id']}: {status}")
            for rank, result in enumerate(question["results"], start=1):
                print(f"  {rank}. {result['citation']} score={result['score']}")
    return 0


def _index_report_payload(report: Any) -> dict[str, Any]:
    payload = asdict(report)
    payload["skipped_files"] = [asdict(skipped) for skipped in report.skipped_files]
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
