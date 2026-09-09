"""Ejecuta planes y guarda cada caso antes de continuar con el siguiente."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import importlib
import time
from dataclasses import asdict
from typing import Any

from eval.config import ExperimentPlan, load_plan, repo_path
from eval.metrics import _build_summary, _classify_errors
from eval.reporting import regenerate_reports
from mia_agents._env import load_env_files
from mia_world.goals import check_goal
from mia_world.scenarios import load_scenario
from mia_world.state import Scenario
from mia_world.tools import make_world_tools


def _agent_config(args: argparse.Namespace, prompt: str | None) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if prompt is not None:
        config["system_prompt"] = prompt
    if args.max_iterations is not None:
        config["max_iterations"] = args.max_iterations
    if args.max_history_messages is not None:
        config["max_history_messages"] = args.max_history_messages
    # Transmitir tambien False: omitirlo activa el default True del agente.
    config["use_structured_memory"] = getattr(args, "use_structured_memory", False)
    config["use_completion_review"] = getattr(args, "use_completion_review", False)
    return config


def _run_one(args: argparse.Namespace, scenario: Scenario, prompt: str | None) -> dict[str, Any]:
    world = scenario.initial_world
    started = time.perf_counter()

    error: str | None = None
    result = None
    agent = None
    stop_on_goal = getattr(args, "stop_on_goal", False)
    try:
        module = importlib.import_module(args.module)
        if not hasattr(module, "build_agent"):
            raise RuntimeError(f"El modulo {args.module!r} no exporta `build_agent`.")

        config = _agent_config(args, prompt)
        if stop_on_goal:
            config["goal_checker"] = lambda: check_goal(world, scenario.goal)
        agent = module.build_agent(config)
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
        "stop_on_goal": stop_on_goal,
        "use_completion_review": getattr(args, "use_completion_review", False),
        "completion_reviews": getattr(agent, "completion_reviews", 0),
        "termination_reason": "runner_error" if error is not None else getattr(agent, "termination_reason", None),
        "duration_seconds": round(duration_seconds, 3),
        "tool_calls": len(steps),
        "error_categories": error_categories,
        "error": error,
        "agent_result": agent_result,
    }



def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _code_metadata() -> dict:
    def git(*args):
        try:
            return subprocess.check_output(["git", *args], cwd=ROOT_DIR,
                                           text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    # Incluye cambios locales y archivos nuevos; el commit solo no alcanza.
    digests = {}
    for folder in ("eval", "student_framework", "mia_agents", "mia_world"):
        for path in sorted((ROOT_DIR / folder).rglob("*.py")):
            digests[path.relative_to(ROOT_DIR).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    status = git("status", "--porcelain")
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None,
            "source_sha256": digests}


def _provider_metadata() -> dict:
    load_env_files()
    # Lista explicita: nunca guardar credenciales ni el entorno completo.
    if os.environ.get("OLLAMA_HOST"):
        return {"provider": "ollama", "model": os.environ.get("OLLAMA_MODEL", "llama3.1"),
                "temperature": 0.2}
    return {"provider": "bedrock", "model": os.environ.get("BEDROCK_MODEL_ID"),
            "region": os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "temperature": 0.2}


def _prepare(plan: ExperimentPlan, scenarios_dir: Path) -> tuple[list[dict], list[dict]]:
    variants = plan.resolved_variants()
    scenarios = []
    for path in sorted(scenarios_dir.glob("*.json")):
        scenario = load_scenario(path)  # Validar antes de crear resultados o llamar al LLM.
        scenarios.append({"id": scenario.id, "source": str(path),
                          "definition": json.loads(path.read_text(encoding="utf-8"))})
    ids = [s["id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("El dataset contiene ids de escenarios duplicados")
    if plan.scenarios != "all":
        missing = set(plan.scenarios) - set(ids)
        if missing:
            raise ValueError(f"Escenarios inexistentes: {sorted(missing)}")
        by_id = {s["id"]: s for s in scenarios}
        scenarios = [by_id[identifier] for identifier in plan.scenarios]
    if not scenarios:
        raise ValueError("No hay escenarios para evaluar")
    return variants, scenarios


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--experiments", help="Plan JSON de experimentos.")
    mode.add_argument("--report", help="Regenerar reportes de una carpeta existente, sin llamar al LLM.")
    parser.add_argument("--dry-run", action="store_true", help="Validar y mostrar el plan sin ejecutarlo.")
    parser.add_argument("--output-root", default="eval/results", help="Raiz para carpetas nuevas por ejecucion.")
    parser.add_argument("--scenarios-dir", default="scenarios")
    parser.add_argument("--module", default="student_framework")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.report:
        if args.dry_run:
            parser.error("--dry-run se usa con --experiments")
        regenerate_reports(repo_path(args.report))
        print(f"Reportes regenerados: {repo_path(args.report)}")
        return 0
    try:
        plan = load_plan(args.experiments)
        variants, scenarios = _prepare(plan, repo_path(args.scenarios_dir))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    total = len(variants) * len(scenarios) * plan.repetitions
    if args.dry_run:
        print(json.dumps({"name": plan.name, "scenarios": [s["id"] for s in scenarios],
                          "repetitions": plan.repetitions, "total_cases": total,
                          "variants": [{k: v for k, v in variant.items() if k != "system_prompt"}
                                       for variant in variants]}, indent=2, ensure_ascii=False))
        return 0

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    destination = repo_path(args.output_root) / plan.name / run_id
    destination.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "run_id": run_id, "name": plan.name,
                "started_at": _utc_now(), "status": "running", "completed_cases": 0,
                "expected_cases": total, "module": args.module,
                "plan": plan.model_dump(), "variants": variants, "scenarios": scenarios,
                "code": _code_metadata(), "llm": _provider_metadata()}
    _write_json(destination / "manifest.json", manifest)
    print(f"Resultados: {destination} ({total} casos)", file=sys.stderr)
    rows = []
    try:
        # Las copias fijan el dataset para toda la corrida y permiten reproducirlo.
        snapshot_dir = destination / "scenarios"
        snapshot_dir.mkdir()
        for index, scenario in enumerate(scenarios):
            _write_json(snapshot_dir / f"{index:03d}.json", scenario["definition"])
        with (destination / "results.jsonl").open("x", encoding="utf-8") as stream:
            for repetition in range(1, plan.repetitions + 1):
                for variant in variants:
                    config = argparse.Namespace(module=args.module, **variant)
                    for index, scenario in enumerate(scenarios):
                        print(f"[{len(rows) + 1}/{total}] {variant['id']} / repeticion {repetition} / {scenario['id']}", file=sys.stderr)
                        fresh_scenario = load_scenario(snapshot_dir / f"{index:03d}.json")
                        row = _run_one(config, fresh_scenario, variant["system_prompt"])
                        row.update(variant=variant["id"], repetition=repetition, completed_at=_utc_now())
                        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                        stream.flush()
                        os.fsync(stream.fileno())
                        rows.append(row)
                        manifest["completed_cases"] = len(rows)
                        _write_json(destination / "manifest.json", manifest)
        manifest["status"] = "completed"
    except BaseException:
        manifest["status"] = "interrupted"
        raise
    finally:
        manifest["finished_at"] = _utc_now()
        _write_json(destination / "manifest.json", manifest)
        if (destination / "results.jsonl").exists():
            regenerate_reports(destination)
    print(f"Evaluacion guardada en {destination}")
    return 1 if any(row["error"] is not None or not row["goal_achieved"] for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
