import json

import pytest
from pydantic import ValidationError

from eval import run
from eval.config import ExperimentPlan
from eval.reporting import regenerate_reports
from mia_agents.testing import MockLLMClient
from mia_agents.types import LLMResponse, ToolCall
from student_framework import build_agent


def plan_data():
    return {"name": "test", "scenarios": ["study-with-key"], "repetitions": 2,
            "defaults": {"use_structured_memory": True},
            "variants": [{"id": "without", "use_structured_memory": False}, {"id": "with"}]}


@pytest.mark.parametrize("value", ["false", 0, None])
def test_rejects_invalid_boolean(value):
    data = plan_data()
    data["variants"][0]["use_structured_memory"] = value
    with pytest.raises(ValidationError):
        ExperimentPlan.model_validate(data)


@pytest.mark.parametrize("change", [
    {"repetitions": 0}, {"scenarios": []},
    {"variants": [{"id": "same"}, {"id": "same"}]},
    {"variants": [{"id": "../escape"}]},
    {"variants": [{"id": "x", "results_dir": "somewhere"}]},
    {"variants": [{"id": "x", "max_iterations": 0}]},
])
def test_rejects_invalid_plan(change):
    with pytest.raises(ValidationError):
        ExperimentPlan.model_validate({**plan_data(), **change})


def test_false_overrides_defaults_and_reaches_agent():
    variants = ExperimentPlan.model_validate(plan_data()).resolved_variants()
    for variant, expected in zip(variants, [False, True]):
        config = run._agent_config(run.argparse.Namespace(**variant), variant["system_prompt"])
        config["llm_client"] = MockLLMClient([])
        assert (build_agent(config)._world_memory is not None) is expected


@pytest.fixture
def evaluation(tmp_path, monkeypatch):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan_data()), encoding="utf-8")
    output = tmp_path / "output"
    monkeypatch.setattr(run, "_provider_metadata", lambda: {"provider": "mock"})
    return path, output, ["--experiments", str(path), "--output-root", str(output)]


def fake_result(args, scenario, prompt):
    # Cada caso debe recibir un mundo limpio, incluso entre repeticiones.
    assert not scenario.initial_world.inventory
    scenario.initial_world.inventory.append("test_marker")
    return {"scenario": scenario.id, "difficulty": scenario.difficulty,
            "goal_achieved": True, "goal_reason": "test", "error": None,
            "duration_seconds": 1.0, "tool_calls": 2, "error_categories": [],
            "agent_result": {"steps": [], "input_tokens": 3, "output_tokens": 4}}


def test_dry_run_creates_nothing_and_calls_no_agent(evaluation, monkeypatch, capsys):
    _, output, args = evaluation
    monkeypatch.setattr(run, "_run_one", lambda *a: pytest.fail("No debe ejecutar"))
    assert run.main(args + ["--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["total_cases"] == 4
    assert not output.exists()


def test_runs_are_isolated_and_reports_regenerate(evaluation, monkeypatch):
    _, output, args = evaluation
    monkeypatch.setattr(run, "_run_one", fake_result)
    for _ in range(2):
        assert run.main(args) == 0
    folders = list((output / "test").iterdir())
    assert len(folders) == 2
    for folder in folders:
        rows = [json.loads(line) for line in (folder / "results.jsonl").read_text().splitlines()]
        assert [(r["variant"], r["repetition"]) for r in rows] == [("without", 1), ("with", 1), ("without", 2), ("with", 2)]
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "completed"
        assert manifest["variants"][0]["system_prompt"]
        assert manifest["scenarios"][0]["definition"]["id"] == "study-with-key"
        before = (folder / "summary.json").read_bytes()
        monkeypatch.setattr(run, "_run_one", lambda *a: pytest.fail("No debe ejecutar"))
        assert run.main(["--report", str(folder)]) == 0
        assert (folder / "summary.json").read_bytes() == before
        summary = json.loads(before)
        assert summary["completed_cases"] == 4
        assert summary["variants"][0]["summary"]["input_tokens"] == 6
        assert summary["variants"][0]["summary"]["by_scenario"]["study-with-key"]["passed"] == 2


def test_interruption_preserves_completed_cases(evaluation, monkeypatch):
    _, output, args = evaluation
    count = 0
    def interrupted(*a):
        nonlocal count
        count += 1
        if count == 2:
            # El primer caso ya esta persistido antes de empezar el siguiente.
            folder = next((output / "test").iterdir())
            assert len((folder / "results.jsonl").read_text().splitlines()) == 1
            raise KeyboardInterrupt()
        return fake_result(*a)
    monkeypatch.setattr(run, "_run_one", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run.main(args)
    folder = next((output / "test").iterdir())
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "interrupted"
    assert manifest["completed_cases"] == 1
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert summary["completed_cases"] == 1
    assert summary["expected_cases"] == 4
    # Un corte abrupto puede dejar una ultima linea truncada.
    with (folder / "results.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"variant":')
    regenerate_reports(folder)
    assert json.loads((folder / "summary.json").read_text(encoding="utf-8"))["completed_cases"] == 1


def test_missing_scenario_fails_before_output(evaluation):
    path, output, args = evaluation
    data = plan_data()
    data["scenarios"] = ["missing"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SystemExit):
        run.main(args)
    assert not output.exists()


@pytest.mark.parametrize("stop_on_goal", [False, True])
def test_full_runner_with_real_agent_and_mock_llm(evaluation, monkeypatch, stop_on_goal):
    import student_framework
    path, output, args = evaluation
    data = plan_data()
    data["repetitions"] = 1
    data["defaults"]["stop_on_goal"] = stop_on_goal
    path.write_text(json.dumps(data), encoding="utf-8")
    original_build = student_framework.build_agent
    clients = []

    def build(config):
        # El mundo real exige revelar, tomar y usar la llave.
        definition = json.loads((run.ROOT_DIR / "scenarios/01-study-with-key.json").read_text(encoding="utf-8"))
        key = definition["items"]["puerta_principal"]["locked"]["requires_item"]
        container = definition["items"][key]["hidden_by"]
        actions = [("look", {}), ("examine", {"target": container}),
                   ("take", {"item": key}), ("use", {"item": key, "target": "puerta_principal"})]
        client = MockLLMClient([
            LLMResponse(None, [ToolCall(str(i), name, json.dumps(kwargs))], input_tokens=2, output_tokens=1)
            for i, (name, kwargs) in enumerate(actions)
        ] + [LLMResponse("Resuelto", input_tokens=2, output_tokens=1)])
        clients.append(client)
        return original_build({**config, "llm_client": client})

    monkeypatch.setattr(student_framework, "build_agent", build)
    assert run.main(args) == 0
    folder = next((output / "test").iterdir())
    rows = [json.loads(line) for line in (folder / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(clients) == 2
    assert all(row["goal_achieved"] and row["tool_calls"] == 4 for row in rows)
    assert all(row["agent_result"]["input_tokens"] == (8 if stop_on_goal else 10) for row in rows)
    assert all(row["stop_on_goal"] is stop_on_goal for row in rows)
    assert all(row["termination_reason"] == ("goal_achieved" if stop_on_goal else "model_response") for row in rows)
    assert "Memoria estructurada observada del entorno:" not in clients[0].calls[-1]["system"]
    assert "Memoria estructurada observada del entorno:" in clients[1].calls[-1]["system"]
