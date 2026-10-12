"""Evaluate fixed questions against a RepoSage index."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from reposage.retrieval import search


def evaluate(
    db_path: str | Path,
    fixture_path: str | Path,
    *,
    top_k: int = 5,
) -> dict[str, Any]:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    question_results: list[dict[str, Any]] = []

    for question in fixture["questions"]:
        results = search(db_path, question["question"], top_k=top_k)
        result_dicts = [asdict(result) for result in results]
        hit = _has_supporting_chunk(result_dicts, question["expected_locations"])
        question_results.append(
            {
                "id": question["id"],
                "question": question["question"],
                "hit": hit,
                "expected_locations": question["expected_locations"],
                "results": result_dicts,
            },
        )

    hits = sum(1 for result in question_results if result["hit"])
    return {
        "fixture": str(fixture_path),
        "top_k": top_k,
        "hits": hits,
        "total": len(question_results),
        "questions": question_results,
    }


def _has_supporting_chunk(
    results: list[dict[str, Any]],
    expected_locations: list[dict[str, Any]],
) -> bool:
    for result in results:
        for expected in expected_locations:
            if result["path"] != expected["path"]:
                continue
            if (
                result["start_line"] <= expected["start_line"]
                and result["end_line"] >= expected["end_line"]
            ):
                return True
    return False
