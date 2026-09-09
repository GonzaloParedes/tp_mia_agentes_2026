from __future__ import annotations

import unicodedata
from typing import Any

def _step_output(step: dict[str, Any]) -> str:
    return str(step.get("tool_output") or "")


def _normalized_lower(text: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return without_accents.lower()


def _step_key(step: dict[str, Any]) -> tuple[str | None, str | None]:
    return step.get("tool_name"), step.get("tool_input")


def _opened_main_door(step: dict[str, Any]) -> bool:
    if step.get("tool_name") != "use":
        return False
    raw_input = str(step.get("tool_input") or "")
    if "puerta_principal" not in raw_input:
        return False
    output = _normalized_lower(_step_output(step))
    return "se abre" in output or "esta abierta" in output or "ya esta abierta" in output


def _classify_errors(
    *,
    row_error: str | None,
    goal_achieved: bool,
    agent_result: dict[str, Any] | None,
    steps: list[dict[str, Any]],
) -> list[str]:
    categories: set[str] = set()

    if row_error is not None:
        categories.add("runner_error")
    if not goal_achieved:
        categories.add("unsolved")

    answer = _normalized_lower(str((agent_result or {}).get("answer") or ""))
    if "limite de iteraciones" in answer:
        categories.add("max_iterations")

    seen_calls: set[tuple[str | None, str | None]] = set()
    previous_key: tuple[str | None, str | None] | None = None
    consecutive_look = 0
    opened_at: int | None = None

    for index, step in enumerate(steps):
        name = step.get("tool_name")
        output = _step_output(step)
        output_lower = _normalized_lower(output)

        if output.startswith("Error:") or step.get("error"):
            categories.add("tool_error")

        if name == "go" and output.startswith("Error:"):
            categories.add("navigation_error")

        if "no llevas" in output_lower:
            categories.add("missing_inventory_item")

        if "no ves" in output_lower or "no es visible" in output_lower:
            categories.add("target_not_visible")

        key = _step_key(step)
        if key in seen_calls:
            categories.add("repeated_action")
        seen_calls.add(key)

        if previous_key == key:
            categories.add("consecutive_repeated_action")
        previous_key = key

        if name == "look":
            consecutive_look += 1
            if consecutive_look >= 2:
                categories.add("repeated_look")
        else:
            consecutive_look = 0

        if opened_at is None and _opened_main_door(step):
            opened_at = index

    if opened_at is not None and opened_at < len(steps) - 1:
        categories.add("post_goal_overrun")

    return sorted(categories)


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    passed = sum(1 for row in rows if row["goal_achieved"] and row["error"] is None)
    failed = total - passed

    by_difficulty: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_difficulty.setdefault(
            row["difficulty"],
            {"total": 0, "passed": 0, "failed": 0, "success_rate": 0.0},
        )
        bucket["total"] += 1
        if row["goal_achieved"] and row["error"] is None:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    for bucket in by_difficulty.values():
        bucket["success_rate"] = (
            round(bucket["passed"] / bucket["total"], 3)
            if bucket["total"]
            else 0.0
        )

    total_tool_calls = sum(row["tool_calls"] for row in rows)
    total_duration = sum(row["duration_seconds"] for row in rows)
    input_tokens = sum(
        (row.get("agent_result") or {}).get("input_tokens") or 0 for row in rows
    )
    output_tokens = sum(
        (row.get("agent_result") or {}).get("output_tokens") or 0 for row in rows
    )
    error_categories: dict[str, int] = {}
    for row in rows:
        for category in row.get("error_categories", []):
            error_categories[category] = error_categories.get(category, 0) + 1

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": round(passed / total, 3) if total else 0.0,
        "by_difficulty": by_difficulty,
        "total_tool_calls": total_tool_calls,
        "avg_tool_calls": round(total_tool_calls / total, 2) if total else 0.0,
        "total_duration_seconds": round(total_duration, 3),
        "avg_duration_seconds": round(total_duration / total, 3) if total else 0.0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "error_categories": dict(sorted(error_categories.items())),
        "failed_scenarios": [
            {
                "scenario": row["scenario"],
                "difficulty": row["difficulty"],
                "goal_reason": row["goal_reason"],
                "error": row["error"],
                "error_categories": row.get("error_categories", []),
            }
            for row in rows
            if not row["goal_achieved"] or row["error"] is not None
        ],
    }


