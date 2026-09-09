from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results" / "latest"


def _normalized_lower(text: str) -> str:
    without_accents = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return without_accents.lower()


def _load_results(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _step_output(step: dict[str, Any]) -> str:
    return str(step.get("tool_output") or "")


def _step_key(step: dict[str, Any]) -> tuple[str | None, str | None]:
    return step.get("tool_name"), step.get("tool_input")


def _has_progress(steps: list[dict[str, Any]]) -> bool:
    progress_patterns = (
        "tomas ",
        "se abre",
        "llegas a ",
        "contiene:",
        "colocas ",
    )
    return any(
        any(pattern in _normalized_lower(_step_output(step)) for pattern in progress_patterns)
        for step in steps
    )


def _count_tool_errors(steps: list[dict[str, Any]]) -> int:
    return sum(1 for step in steps if _step_output(step).startswith("Error:") or step.get("error"))


def _count_repeated_calls(steps: list[dict[str, Any]]) -> int:
    seen: set[tuple[str | None, str | None]] = set()
    repeated = 0
    for step in steps:
        key = _step_key(step)
        if key in seen:
            repeated += 1
        seen.add(key)
    return repeated


def _count_consecutive_repeats(steps: list[dict[str, Any]]) -> int:
    previous: tuple[str | None, str | None] | None = None
    repeated = 0
    for step in steps:
        key = _step_key(step)
        if key == previous:
            repeated += 1
        previous = key
    return repeated


def _count_openings(steps: list[dict[str, Any]]) -> int:
    return sum(1 for step in steps if "se abre" in _normalized_lower(_step_output(step)))


def _count_taken_items(steps: list[dict[str, Any]]) -> int:
    return sum(1 for step in steps if step.get("tool_name") == "take" and "tomas " in _normalized_lower(_step_output(step)))


def _has_runner_error(row: dict[str, Any]) -> bool:
    return row.get("error") is not None or "runner_error" in row.get("error_categories", [])


def _score_row(row: dict[str, Any]) -> tuple[int, str]:
    steps = (row.get("agent_result") or {}).get("steps") or []
    categories = set(row.get("error_categories") or [])
    achieved = bool(row.get("goal_achieved")) and row.get("error") is None

    if _has_runner_error(row) or not steps:
        return 0, "No hay trayectoria evaluable por error de runner o ausencia de steps."

    tool_errors = _count_tool_errors(steps)
    repeated_calls = _count_repeated_calls(steps)
    consecutive_repeats = _count_consecutive_repeats(steps)
    openings = _count_openings(steps)
    taken_items = _count_taken_items(steps)
    progress = _has_progress(steps)

    if achieved:
        severe_noise = consecutive_repeats >= 3 or repeated_calls >= 8 or "post_goal_overrun" in categories
        if severe_noise:
            return 2, (
                "Resuelve el objetivo, pero con repeticiones importantes o acciones posteriores "
                "al cumplimiento."
            )
        if tool_errors >= 4 or repeated_calls >= 4:
            return 2, "Resuelve el objetivo, aunque requiere varias correcciones de errores locales."
        return 3, "Resuelve con trayectoria coherente y sin repeticiones graves."

    if not progress:
        return 0, "No resuelve y no muestra progreso observable en la trayectoria."

    if "max_iterations" in categories or repeated_calls >= 3 or consecutive_repeats >= 2:
        if openings or taken_items >= 2:
            return 2, "Progresa en subobjetivos, pero falla por limite de iteraciones, orden o memoria."
        return 1, "Explora parcialmente, pero se atasca en repeticiones o errores."

    if openings or taken_items >= 2:
        return 2, "No resuelve, pero completa subobjetivos relevantes."
    return 1, "No resuelve; hay progreso limitado pero insuficiente."


def _review_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = []
    for row in rows:
        score, reason = _score_row(row)
        reviews.append(
            {
                "variant": row.get("variant", "legacy"),
                "repetition": row.get("repetition", 1),
                "scenario": row.get("scenario"),
                "difficulty": row.get("difficulty"),
                "goal_achieved": row.get("goal_achieved"),
                "tool_calls": row.get("tool_calls"),
                "error_categories": row.get("error_categories", []),
                "qualitative_score": score,
                "qualitative_reason": reason,
                "evidence": {
                    "tool_errors": _count_tool_errors((row.get("agent_result") or {}).get("steps") or []),
                    "repeated_calls": _count_repeated_calls((row.get("agent_result") or {}).get("steps") or []),
                    "consecutive_repeats": _count_consecutive_repeats((row.get("agent_result") or {}).get("steps") or []),
                    "termination_reason": row.get("termination_reason"),
                },
            }
        )

    total = len(reviews)
    average = round(sum(row["qualitative_score"] for row in reviews) / total, 3) if total else 0.0
    distribution: dict[str, int] = {}
    for row in reviews:
        key = str(row["qualitative_score"])
        distribution[key] = distribution.get(key, 0) + 1

    by_variant = {}
    for variant in sorted({r["variant"] for r in reviews}):
        selected = [r for r in reviews if r["variant"] == variant]
        by_repetition = {}
        for rep in sorted({r["repetition"] for r in selected}):
            scores = [r["qualitative_score"] for r in selected if r["repetition"] == rep]
            by_repetition[str(rep)] = round(sum(scores) / len(scores), 3)
        by_variant[variant] = {
            "total": len(selected),
            "average_qualitative_score": round(sum(r["qualitative_score"] for r in selected) / len(selected), 3),
            "by_repetition": by_repetition,
        }

    return {
        "rubric_version": "1.0",
        "rubric": {
            "0": "No progresa o no hay trayectoria evaluable.",
            "1": "Progresa poco, se atasca o repite errores.",
            "2": "Progresa parcialmente o resuelve con ruido importante.",
            "3": "Resuelve con trayectoria coherente y sin repeticiones graves.",
        },
        "total": total,
        "average_qualitative_score": average,
        "score_distribution": dict(sorted(distribution.items())),
        "by_variant": by_variant,
        "reviews": reviews,
    }


def _write_markdown(review: dict[str, Any], path: Path) -> None:
    lines = [
        "# Qualitative Review",
        "",
        f"- Total casos: {review['total']}",
        f"- Average qualitative score: {review['average_qualitative_score']}",
        f"- Score distribution: {review['score_distribution']}",
        "",
        "Los puntajes son heuristicas de trayectoria, no evaluan directamente la calidad de la respuesta final.",
        "",
        "| Variante | Promedio | Casos |",
        "| --- | ---: | ---: |",
    ]
    for variant, summary in review["by_variant"].items():
        lines.append(f"| {variant} | {summary['average_qualitative_score']} | {summary['total']} |")
    lines.extend(["", "| Variante | Repeticion | Scenario | Difficulty | Goal | Score | Reason |",
                  "| --- | ---: | --- | --- | --- | ---: | --- |"])
    for row in review["reviews"]:
        reason = re.sub(r"\s+", " ", row["qualitative_reason"]).strip()
        lines.append(
            f"| {row['variant']} | {row['repetition']} | {row['scenario']} | {row['difficulty']} | {row['goal_achieved']} | "
            f"{row['qualitative_score']} | {reason} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Aplica una rubrica cualitativa sobre results.jsonl.")
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Directorio que contiene results.jsonl.",
    )
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    rows = _load_results(results_dir / "results.jsonl")
    review = _review_rows(rows)
    review["source"] = {
        "results_file": str(results_dir / "results.jsonl"),
        "sha256": hashlib.sha256((results_dir / "results.jsonl").read_bytes()).hexdigest(),
    }

    json_path = results_dir / "qualitative_review.json"
    md_path = results_dir / "qualitative_review.md"
    json_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(review, md_path)

    print(json.dumps({k: v for k, v in review.items() if k != "reviews"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
