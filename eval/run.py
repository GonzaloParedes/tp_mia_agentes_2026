from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import unicodedata
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mia_world.goals import check_goal
from mia_world.scenarios import list_scenarios, load_scenario
from mia_world.state import Scenario
from mia_world.tools import make_world_tools
from eval.reporting import write_experiment_comparison


DEFAULT_SCENARIOS_DIR = ROOT_DIR / "scenarios"
DEFAULT_RESULTS_DIR = ROOT_DIR / "eval" / "results" / "latest"
DEFAULT_EXPERIMENTS_DIR = ROOT_DIR / "eval" / "results"
DEFAULT_EXPERIMENTS_RUNS_DIR = DEFAULT_EXPERIMENTS_DIR / "experiments"


def _resolve_scenario(spec: str, scenarios_dir: Path) -> Scenario:
    path = Path(spec)
    if path.is_file():
        return load_scenario(path)

    available = list_scenarios(scenarios_dir)

    by_id = {sc.id: sc for sc in available}
    if spec in by_id:
        return by_id[spec]

    by_diff = [sc for sc in available if sc.difficulty == spec]
    if by_diff:
        return by_diff[0]

    options = ", ".join(sorted(sc.id for sc in available)) or "(ninguno)"
    raise SystemExit(f"No se encontro el escenario {spec!r}. Disponibles: {options}.")


def _load_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise SystemExit(f"No se encontro el prompt en {path}.")


def _resolve_repo_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def _default_experiment_run_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return DEFAULT_EXPERIMENTS_RUNS_DIR / timestamp


def _load_experiments(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"No se encontro el archivo de experimentos en {path}.")
    if not isinstance(data, list):
        raise SystemExit("El archivo de experimentos debe contener una lista JSON.")
    for index, experiment in enumerate(data):
        if not isinstance(experiment, dict):
            raise SystemExit(f"Experimento #{index + 1} no es un objeto JSON.")
        if "id" not in experiment:
            raise SystemExit(f"Experimento #{index + 1} no tiene campo 'id'.")
    return data


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


def _agent_config(args: argparse.Namespace, prompt: str | None) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if prompt is not None:
        config["system_prompt"] = prompt
    if args.max_iterations is not None:
        config["max_iterations"] = args.max_iterations
    if args.max_history_messages is not None:
        config["max_history_messages"] = args.max_history_messages
    if getattr(args, "use_structured_memory", False):
        config["use_structured_memory"] = True
    return config


def _run_one(args: argparse.Namespace, scenario: Scenario, prompt: str | None) -> dict[str, Any]:
    world = scenario.initial_world
    started = time.perf_counter()

    error: str | None = None
    result = None
    try:
        module = importlib.import_module(args.module)
        if not hasattr(module, "build_agent"):
            raise RuntimeError(f"El modulo {args.module!r} no exporta `build_agent`.")

        agent = module.build_agent(_agent_config(args, prompt))
        for fn, schema in make_world_tools(world):
            agent.register_tool(fn, schema)

        result = agent.run(scenario.user_message)
    except Exception as exc:
        error = str(exc)
    duration_seconds = time.perf_counter() - started

    achieved, reason = check_goal(world, scenario.goal)
    agent_result = asdict(result) if result is not None else None
    steps = agent_result["steps"] if agent_result is not None else []
    error_categories = _classify_errors(
        row_error=error,
        goal_achieved=achieved,
        agent_result=agent_result,
        steps=steps,
    )

    return {
        "scenario": scenario.id,
        "difficulty": scenario.difficulty,
        "description": scenario.description,
        "goal": scenario.goal,
        "goal_achieved": achieved,
        "goal_reason": reason,
        "duration_seconds": round(duration_seconds, 3),
        "tool_calls": len(steps),
        "error_categories": error_categories,
        "error": error,
        "agent_result": agent_result,
    }


def _scenarios_for_args(args: argparse.Namespace) -> list[Scenario]:
    scenarios_dir = Path(args.scenarios_dir)
    return (
        [_resolve_scenario(args.scenario, scenarios_dir)]
        if args.scenario
        else list_scenarios(scenarios_dir)
    )


def _run_scenarios(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scenarios = _scenarios_for_args(args)
    prompt = _load_prompt(Path(args.prompt)) if args.prompt else None

    rows = []
    for scenario in scenarios:
        print(f"# Escenario: {scenario.id} ({scenario.difficulty})", file=sys.stderr)
        row = _run_one(args, scenario, prompt)
        rows.append(row)

    summary = _build_summary(rows)
    _write_results(rows, summary, Path(args.results_dir))
    return rows, summary


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


def _aggregate_summaries(run_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(summary["total"] for summary in run_summaries)
    passed = sum(summary["passed"] for summary in run_summaries)
    failed = sum(summary["failed"] for summary in run_summaries)
    total_tool_calls = sum(summary["total_tool_calls"] for summary in run_summaries)
    total_duration = sum(summary["total_duration_seconds"] for summary in run_summaries)
    input_tokens = sum(summary["input_tokens"] for summary in run_summaries)
    output_tokens = sum(summary["output_tokens"] for summary in run_summaries)

    by_difficulty: dict[str, dict[str, Any]] = {}
    error_categories: dict[str, int] = {}
    failed_scenarios = []

    for run_index, summary in enumerate(run_summaries, start=1):
        for difficulty, bucket in summary.get("by_difficulty", {}).items():
            aggregate = by_difficulty.setdefault(
                difficulty,
                {"total": 0, "passed": 0, "failed": 0, "success_rate": 0.0},
            )
            aggregate["total"] += bucket["total"]
            aggregate["passed"] += bucket["passed"]
            aggregate["failed"] += bucket["failed"]

        for category, count in summary.get("error_categories", {}).items():
            error_categories[category] = error_categories.get(category, 0) + count

        for failed_case in summary.get("failed_scenarios", []):
            failed_scenarios.append({"run": run_index, **failed_case})

    for bucket in by_difficulty.values():
        bucket["success_rate"] = (
            round(bucket["passed"] / bucket["total"], 3)
            if bucket["total"]
            else 0.0
        )

    return {
        "runs": len(run_summaries),
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
        "failed_scenarios": failed_scenarios,
    }


def _write_results(rows: list[dict[str, Any]], summary: dict[str, Any], results_dir: Path) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "results.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (results_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evalua el agente sobre un escenario M3.")
    parser.add_argument(
        "--experiments",
        default=None,
        help="Archivo JSON con experimentos a ejecutar. Si se pasa, corre todos los experimentos.",
    )
    parser.add_argument(
        "--scenario",
        default=None,
        help="Escenario por id, dificultad o path. Si se omite, corre todos.",
    )
    parser.add_argument(
        "--module",
        default="student_framework",
        help="Modulo Python que exporta build_agent.",
    )
    parser.add_argument(
        "--scenarios-dir",
        default=str(DEFAULT_SCENARIOS_DIR),
        help="Directorio de escenarios.",
    )
    parser.add_argument(
        "--prompt",
        default=None,
        help="Archivo de system prompt. Si se omite, usa el prompt default del agente.",
    )
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--max-history-messages", type=int, default=None)
    parser.add_argument(
        "--use-structured-memory",
        action="store_true",
        help="Activa memoria estructurada observacional dentro del agente.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Cantidad de repeticiones por experimento cuando se usa --experiments.",
    )
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Directorio donde escribir results.jsonl.",
    )
    parser.add_argument(
        "--experiments-results-dir",
        default=None,
        help="Directorio para una corrida completa de experimentos. Si se omite, usa timestamp.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.runs < 1:
        raise SystemExit("--runs debe ser >= 1.")

    if args.experiments:
        experiments = _load_experiments(_resolve_repo_path(args.experiments))
        experiment_run_dir = (
            _resolve_repo_path(args.experiments_results_dir)
            if args.experiments_results_dir
            else _default_experiment_run_dir()
        )
        experiment_run_dir.mkdir(parents=True, exist_ok=True)
        print(f"## Resultados: {experiment_run_dir}", file=sys.stderr)

        experiment_summaries = []
        any_failed = False
        for experiment in experiments:
            exp_id = str(experiment["id"])
            print(f"## Experimento: {exp_id}", file=sys.stderr)
            exp_args = argparse.Namespace(**vars(args))
            prompt_path = experiment.get("prompt", args.prompt)
            exp_args.prompt = str(_resolve_repo_path(prompt_path)) if prompt_path else None

            max_iterations = experiment.get("max_iterations", args.max_iterations)
            exp_args.max_iterations = int(max_iterations) if max_iterations is not None else None

            max_history_messages = experiment.get(
                "max_history_messages",
                args.max_history_messages,
            )
            exp_args.max_history_messages = (
                int(max_history_messages) if max_history_messages is not None else None
            )

            exp_args.use_structured_memory = bool(
                experiment.get("use_structured_memory", args.use_structured_memory)
            )

            configured_results_dir = experiment.get("results_dir")
            experiment_results_dir = (
                _resolve_repo_path(configured_results_dir)
                if configured_results_dir
                else experiment_run_dir / exp_id
            )

            run_summaries = []
            for run_number in range(1, args.runs + 1):
                print(f"## Repeticion: {run_number}/{args.runs}", file=sys.stderr)
                if args.runs == 1:
                    run_results_dir = experiment_results_dir
                else:
                    run_results_dir = experiment_results_dir / f"run_{run_number:02d}"
                exp_args.results_dir = str(run_results_dir)
                _, run_summary = _run_scenarios(exp_args)
                run_summaries.append(run_summary)

            summary = (
                run_summaries[0]
                if args.runs == 1
                else _aggregate_summaries(run_summaries)
            )
            summary_with_meta = {
                "id": exp_id,
                "description": experiment.get("description", ""),
                "prompt": prompt_path,
                "max_iterations": exp_args.max_iterations,
                "max_history_messages": exp_args.max_history_messages,
                "use_structured_memory": exp_args.use_structured_memory,
                "runs": args.runs,
                "results_dir": str(experiment_results_dir),
                "run_summaries": run_summaries,
                "summary": summary,
            }
            experiment_summaries.append(summary_with_meta)
            if summary["failed"]:
                any_failed = True

        summary_path = experiment_run_dir / "experiments_summary.json"
        comparison_path = experiment_run_dir / "comparison.json"
        plots_path = experiment_run_dir / "comparison.svg"

        summary_path.write_text(
            json.dumps(experiment_summaries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        write_experiment_comparison(
            experiment_summaries,
            comparison_path=comparison_path,
            plots_path=plots_path,
        )
        print(json.dumps(experiment_summaries, indent=2, ensure_ascii=False))
        return 1 if any_failed else 0

    rows, summary = _run_scenarios(args)

    output: dict[str, Any] = rows[0] if args.scenario else summary
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
