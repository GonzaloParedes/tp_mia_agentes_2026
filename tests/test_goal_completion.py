import json
from pathlib import Path

import pytest

from mia_agents.testing import MockLLMClient
from mia_agents.types import LLMResponse, ToolCall
from mia_world.goals import check_goal
from mia_world.scenarios import load_scenario
from mia_world.tools import make_world_tools
from student_framework import build_agent


def office_setup():
    scenario = load_scenario(Path(__file__).resolve().parents[1] / "scenarios/06-hard-office-sequence.json")
    tools = make_world_tools(scenario.initial_world)
    return scenario, tools


def response(actions):
    return LLMResponse(None, [
        ToolCall(str(i), name, json.dumps(args)) for i, (name, args) in enumerate(actions)
    ], input_tokens=10, output_tokens=5)


PREFIX = [
    ("go", {"direction": "este"}),
    ("go", {"direction": "este"}),
    ("examine", {"target": "cajon_llaves"}),
    ("take", {"item": "llave_caja"}),
    ("go", {"direction": "oeste"}),
    ("go", {"direction": "norte"}),
    ("use", {"item": "llave_caja", "target": "caja_fuerte"}),
    ("examine", {"target": "caja_fuerte"}),
    ("take", {"item": "llave_maestra"}),
]
OPEN_DOOR = [
    ("go", {"direction": "sur"}),
    ("go", {"direction": "oeste"}),
    ("use", {"item": "llave_maestra", "target": "puerta_principal"}),
]


@pytest.mark.parametrize("memory", [False, True])
def test_stops_at_full_goal_and_cancels_remaining_batch(memory):
    scenario, tools = office_setup()
    actions = PREFIX + [("take", {"item": "documento_confidencial"})] + OPEN_DOOR
    llm = MockLLMClient([response(actions + [("go", {"direction": "este"})])])
    agent = build_agent({"llm_client": llm, "max_iterations": 1,
                         "use_structured_memory": memory,
                         "goal_checker": lambda: check_goal(scenario.initial_world, scenario.goal)})
    for fn, schema in tools:
        agent.register_tool(fn, schema)
    result = agent.run(scenario.user_message)
    assert check_goal(scenario.initial_world, scenario.goal)[0]
    assert len(result.steps) == len(actions)
    assert result.answer.startswith("Objetivo cumplido:")
    assert agent.termination_reason == "goal_achieved"
    assert (result.input_tokens, result.output_tokens) == (10, 5)
    assert llm.call_count == 1
    # Todos los tool calls reciben respuesta de protocolo, incluso el cancelado.
    replies = [m for m in agent._history if m["role"] == "tool"]
    assert len(replies) == len(actions) + 1
    assert replies[-1]["content"].startswith("No ejecutada:")
    assert agent._history[-1]["content"] == result.answer
    # Volver a consultar un objetivo ya logrado no consume otro llamado al LLM.
    assert agent.run("Confirmar resultado").steps == []
    assert llm.call_count == 1


def test_opening_door_before_document_does_not_complete_sequence():
    scenario, tools = office_setup()
    actions = PREFIX + OPEN_DOOR + [
        ("go", {"direction": "este"}), ("go", {"direction": "norte"}),
        ("take", {"item": "documento_confidencial"}),
    ]
    llm = MockLLMClient([response(actions)])
    agent = build_agent({"llm_client": llm, "max_iterations": 1,
                         "goal_checker": lambda: check_goal(scenario.initial_world, scenario.goal)})
    for fn, schema in tools:
        agent.register_tool(fn, schema)
    result = agent.run(scenario.user_message)
    assert not check_goal(scenario.initial_world, scenario.goal)[0]
    assert "documento_confidencial" in scenario.initial_world.inventory
    assert scenario.initial_world.items["puerta_principal"].open_state == "open"
    assert len(result.steps) == len(actions)
    assert agent.termination_reason == "max_iterations"
    assert not result.answer.startswith("Objetivo cumplido:")


def test_without_checker_agent_keeps_model_termination():
    llm = MockLLMClient([LLMResponse("Respuesta normal")])
    agent = build_agent({"llm_client": llm})
    assert agent.run("Hola").answer == "Respuesta normal"
    assert agent.termination_reason == "model_response"
