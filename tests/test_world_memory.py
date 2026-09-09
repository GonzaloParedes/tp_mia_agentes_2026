import json
from pathlib import Path

import pytest

from mia_agents.testing import MockLLMClient
from mia_agents.types import LLMResponse, ToolCall
from mia_world.scenarios import load_scenario
from mia_world.tools import make_world_tools
from student_framework import build_agent
from student_framework.world_memory import WorldMemory


@pytest.mark.parametrize(
    "filename,container,item",
    [
        ("03-hard-library-search.json", "estanteria_alta", "libro_geometria"),
        ("04-extreme-archive.json", "estanteria_archivo", "expediente_1042"),
    ],
)
def test_agent_learns_non_takeable_objects_from_world(filename, container, item):
    actions = [
        ("look", {}),
        ("examine", {"target": container}),
        ("take", {"item": item}),
        ("examine", {"target": container}),
        ("take", {"item": item}),
        ("examine", {"target": item}),
    ]
    llm = MockLLMClient([
        LLMResponse(None, [ToolCall(str(i), name, json.dumps(args))])
        for i, (name, args) in enumerate(actions)
    ] + [LLMResponse("Fin")])
    agent = build_agent({"llm_client": llm, "use_structured_memory": True})
    scenario = load_scenario(Path(__file__).resolve().parents[1] / "scenarios" / filename)
    for fn, schema in make_world_tools(scenario.initial_world):
        agent.register_tool(fn, schema)
    result = agent.run(scenario.user_message)

    assert "no es algo que puedas llevarte" in result.steps[2].tool_output
    assert "memoria estructurada" in result.steps[4].tool_output
    assert not result.steps[5].tool_output.startswith("Error:")
    memory = agent._world_memory
    assert item in memory.not_takeable
    assert item not in memory.revealed_not_taken
    assert item not in memory.takeable
    assert "Objetos no transportables confirmados" in llm.calls[3]["system"]
    assert memory.validate_action(
        tool_name="use", tool_input=json.dumps({"item": item, "target": container})
    ) is not None


def test_unknown_or_non_takeable_objects_do_not_block_navigation():
    memory = WorldMemory()
    memory.update(tool_name="look", tool_input="{}", error=None,
                  tool_output="Estás en Sala.\nSalidas: norte.")
    memory.update(tool_name="examine", tool_input='{"target":"estante"}', error=None,
                  tool_output="Contiene:\n - Libro [id: libro]")
    assert memory.validate_action(tool_name="go", tool_input='{"direction":"norte"}') is None
    memory.update(tool_name="take", tool_input='{"item":"libro"}', error=None,
                  tool_output="Error: Libro no es algo que puedas llevarte.")
    assert memory.validate_action(tool_name="go", tool_input='{"direction":"norte"}') is None


def test_visibility_error_does_not_mark_item_as_non_takeable():
    memory = WorldMemory()
    memory.update(tool_name="take", tool_input='{"item":"llave"}', error=None,
                  tool_output="Error: 'llave' no es visible o accesible desde aquí.")
    assert memory.validate_action(tool_name="take", tool_input='{"item":"llave"}') is None
    memory.update(tool_name="take", tool_input='{"item":"llave"}', error=None,
                  tool_output="Tomas la llave.")
    assert "llave" in memory.inventory
    assert "llave" in memory.takeable
    assert "llave" not in memory.not_takeable


def test_revealed_key_can_still_be_taken_and_used():
    scenario = load_scenario(
        Path(__file__).resolve().parents[1] / "scenarios" / "01-study-with-key.json"
    )
    tools = {schema.name: fn for fn, schema in make_world_tools(scenario.initial_world)}
    memory = WorldMemory()
    actions = [
        ("look", {}),
        ("examine", {"target": "alfombra"}),
    ]
    for name, args in actions:
        memory.update(tool_name=name, tool_input=json.dumps(args),
                      tool_output=tools[name](**args), error=None)
    key = next(iter(memory.revealed_not_taken))
    args = json.dumps({"item": key})
    assert memory.validate_action(tool_name="take", tool_input=args) is None
    memory.update(tool_name="take", tool_input=args, tool_output=tools["take"](item=key), error=None)
    use_args = {"item": key, "target": "puerta_principal"}
    assert memory.validate_action(tool_name="use", tool_input=json.dumps(use_args)) is None
    assert "Se abre" in tools["use"](**use_args)


def test_look_removes_opened_exit_block_in_real_scenario():
    scenario = load_scenario(
        Path(__file__).resolve().parents[1] / "scenarios" / "08-extreme-backtracking-vault.json"
    )
    tools = {schema.name: fn for fn, schema in make_world_tools(scenario.initial_world)}
    memory = WorldMemory()

    def observe(name, **args):
        memory.update(tool_name=name, tool_input=json.dumps(args),
                      tool_output=tools[name](**args), error=None)

    observe("go", direction="norte")
    observe("look")
    assert memory.rooms["Sala A"].blocked_exits == {"norte": "puerta blindada"}
    observe("examine", target="escritorio")
    observe("take", item="llave_intermedia")
    observe("use", item="llave_intermedia", target="puerta_blindada")
    observe("look")
    assert memory.rooms["Sala A"].exits == {"norte", "sur"}
    assert memory.rooms["Sala A"].blocked_exits == {}
    assert "norte bloqueada" not in memory.to_prompt()
    observe("go", direction="norte")
    observe("look")
    assert memory.rooms["Sala B"].blocked_exits == {"norte": "reja"}
    observe("go", direction="sur")
    observe("look")
    assert memory.rooms["Sala A"].blocked_exits == {}
    assert memory.rooms["Sala B"].blocked_exits == {"norte": "reja"}


def test_new_exit_observation_preserves_remaining_blocks():
    memory = WorldMemory()
    for output in [
        "Estás en Sala.\nSalidas: norte (bloqueada por puerta), sur (bloqueada por reja).",
        "Estás en Sala.\nSalidas: norte, sur (bloqueada por reja).",
    ]:
        memory.update(tool_name="look", tool_input="{}", tool_output=output, error=None)
    assert memory.rooms["Sala"].blocked_exits == {"sur": "reja"}
    assert memory.rooms["Sala"].exits == {"norte", "sur"}
