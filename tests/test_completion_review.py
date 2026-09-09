import json

import pytest

from mia_agents.testing import MockLLMClient
from mia_agents.types import LLMResponse, ToolCall, ToolSchema
from student_framework import build_agent


def action(name, **args):
    return LLMResponse(None, [ToolCall(name, name, json.dumps(args))], input_tokens=2, output_tokens=1)


def test_premature_answer_can_resume_but_is_reviewed_only_once():
    llm = MockLLMClient([
        LLMResponse("Debo considerar otras estrategias.", input_tokens=2, output_tokens=1),
        action("calculator", a=2, b=3, operator="+"),
        LLMResponse("El resultado es 5.", input_tokens=2, output_tokens=1),
    ])
    agent = build_agent({"llm_client": llm, "use_completion_review": True})
    result = agent.run("Calcula 2 + 3 con la herramienta.")
    assert result.answer == "El resultado es 5."
    assert len(result.steps) == 1
    assert agent.completion_reviews == 1
    assert llm.call_count == 3
    assert (result.input_tokens, result.output_tokens) == (6, 3)
    assert "respuesta_propuesta" in llm.calls[1]["system"]
    assert "respuesta_propuesta" not in llm.calls[2]["system"]


@pytest.mark.parametrize("limit,expected_calls", [(1, 1), (2, 2)])
def test_review_respects_budget_and_accepts_honest_failure(limit, expected_calls):
    llm = MockLLMClient([LLMResponse("No tengo informacion suficiente.")] * expected_calls)
    agent = build_agent({"llm_client": llm, "use_completion_review": True, "max_iterations": limit})
    result = agent.run("Resuelve la tarea.")
    assert llm.call_count == expected_calls
    assert result.answer == "No tengo informacion suficiente."
    assert agent.completion_reviews == expected_calls - 1
    assert agent.termination_reason == "model_response"


def test_review_cannot_extend_tool_loop_beyond_budget():
    llm = MockLLMClient([LLMResponse("Voy a calcular."), action("calculator", a=2, b=3, operator="+")])
    agent = build_agent({"llm_client": llm, "use_completion_review": True, "max_iterations": 2})
    result = agent.run("Calcula.")
    assert llm.call_count == 2
    assert len(result.steps) == 1
    assert agent.termination_reason == "max_iterations"


def test_review_sees_observed_order_even_with_small_history_without_oracle():
    def take(item: str) -> str:
        """Toma un objeto."""
        return f"Tomas {item}."

    def use(item: str, target: str) -> str:
        """Usa un objeto."""
        return f"Usas {item} con {target}. Se abre."

    llm = MockLLMClient([
        action("take", item="documento"),
        action("use", item="llave", target="puerta"),
        LLMResponse("Recogi el documento y abri la puerta."),
        LLMResponse("Recogi el documento antes de abrir la puerta."),
    ])
    agent = build_agent({"llm_client": llm, "use_completion_review": True,
                         "use_structured_memory": False, "max_history_messages": 1})
    for fn in (take, use):
        agent.register_tool(fn, ToolSchema.from_callable(fn))
    request = "Recoge el documento antes de abrir la puerta."
    result = agent.run(request)
    assert agent._goal_checker is None
    context = llm.calls[2]["system"]
    assert request in context
    assert context.index("Tomas documento.") < context.index("Usas llave con puerta.")
    assert all(len(call["messages"]) <= 1 for call in llm.calls)
    assert result.answer == "Recogi el documento antes de abrir la puerta."
    assert agent.termination_reason == "model_response"


def test_disabling_review_preserves_original_behavior():
    llm = MockLLMClient([LLMResponse("Respuesta")])
    agent = build_agent({"llm_client": llm, "use_completion_review": False})
    assert agent.run("Pregunta").answer == "Respuesta"
    assert llm.call_count == 1
    assert agent.completion_reviews == 0
    assert "Revision de finalizacion basada solo en observaciones" not in llm.calls[0]["system"]


@pytest.mark.parametrize("empty", [None, "", " \n\t"])
def test_empty_review_preserves_immediately_previous_draft(empty):
    draft = "No tengo informacion suficiente para completar la tarea."
    llm = MockLLMClient([
        LLMResponse(draft, input_tokens=3, output_tokens=2),
        LLMResponse(empty, input_tokens=4, output_tokens=0),
    ])
    agent = build_agent({"llm_client": llm, "use_completion_review": True})
    result = agent.run("Resuelve la tarea.")
    assert result.answer == draft
    assert result.error is None
    assert agent.termination_reason == "review_empty_fallback"
    assert agent._history[-1]["content"] == draft
    assert (result.input_tokens, result.output_tokens) == (7, 2)
    assert llm.call_count == 2


@pytest.mark.parametrize("review", [False, True])
def test_empty_responses_without_draft_report_explicit_failure(review):
    llm = MockLLMClient([LLMResponse(None), LLMResponse("  ")] if review else [LLMResponse(None)])
    agent = build_agent({"llm_client": llm, "use_completion_review": review})
    result = agent.run("Resuelve la tarea.")
    assert result.error == "empty_response"
    assert agent.termination_reason == "empty_response"
    assert "no puedo confirmar" in result.answer
    assert agent._history[-1]["content"] == result.answer
    assert all(m.get("content", "").strip() for m in agent._history)
    assert llm.call_count == (2 if review else 1)


def test_draft_is_not_reused_after_tools_resume():
    llm = MockLLMClient([
        LLMResponse("Voy a calcular."),
        action("calculator", a=2, b=3, operator="+"),
        LLMResponse(None),
    ])
    agent = build_agent({"llm_client": llm, "use_completion_review": True})
    result = agent.run("Calcula 2 + 3.")
    assert result.answer != "Voy a calcular."
    assert result.error == "empty_response"
    assert len(result.steps) == 1
    assert llm.call_count == 3


def test_empty_review_at_budget_limit_preserves_draft():
    llm = MockLLMClient([LLMResponse("Respuesta previa."), LLMResponse(None)])
    agent = build_agent({"llm_client": llm, "use_completion_review": True, "max_iterations": 2})
    assert agent.run("Pregunta.").answer == "Respuesta previa."
    assert llm.call_count == 2


def test_previous_turn_answer_is_not_used_for_empty_new_turn():
    llm = MockLLMClient([LLMResponse("Respuesta anterior."), LLMResponse(None),
                         LLMResponse(None), LLMResponse(None)])
    agent = build_agent({"llm_client": llm, "use_completion_review": True})
    assert agent.run("Primera pregunta.").answer == "Respuesta anterior."
    assert agent.run("Otra pregunta.").error == "empty_response"
