"""Tests propios para las tools de student_framework y casos borde del agente."""

from __future__ import annotations

import pytest

from mia_agents.testing import MockLLMClient
from mia_agents.types import LLMResponse

from student_framework import build_agent
from student_framework.tools.calculator import calculator
from student_framework.tools.file_reader import file_reader
from student_framework.tools.text_search import text_search


# ---------------------------------------------------------------------------
# calculator
# ---------------------------------------------------------------------------

def test_calculator_suma():
    assert calculator(3, 4, "+") == "7"

def test_calculator_resta():
    assert calculator(10, 3, "-") == "7"

def test_calculator_multiplicacion():
    assert calculator(6, 7, "*") == "42"

def test_calculator_modulo():
    assert calculator(10, 3, "%") == "1"

def test_calculator_modulo_por_cero():
    resultado = calculator(5, 0, "%")
    assert "Error" in resultado

def test_calculator_precision_float():
    # 0.1 + 0.2 no da 0.3 exacto en float — documentamos el comportamiento real
    resultado = calculator(0.1, 0.2, "+")
    assert resultado != "0.3"  # limitación conocida de float


# ---------------------------------------------------------------------------
# file_reader
# ---------------------------------------------------------------------------

def test_file_reader_archivo_normal(tmp_path):
    archivo = tmp_path / "hola.txt"
    archivo.write_text("contenido de prueba", encoding="utf-8")
    assert file_reader(str(archivo)) == "contenido de prueba"

def test_file_reader_archivo_vacio(tmp_path):
    archivo = tmp_path / "vacio.txt"
    archivo.write_text("", encoding="utf-8")
    assert file_reader(str(archivo)) == ""

def test_file_reader_no_encontrado():
    resultado = file_reader("/ruta/inexistente/archivo.txt")
    assert "Error" in resultado

def test_file_reader_es_directorio(tmp_path):
    resultado = file_reader(str(tmp_path))
    assert "Error" in resultado

# ---------------------------------------------------------------------------
# text_search
# ---------------------------------------------------------------------------

def test_text_search_encuentra_coincidencia(tmp_path):
    archivo = tmp_path / "log.txt"
    archivo.write_text("ERROR en linea 1\nTodo bien\nERROR en linea 3", encoding="utf-8")
    resultado = text_search(str(archivo), "ERROR")
    assert "Línea 1" in resultado
    assert "Línea 3" in resultado
    assert "Línea 2" not in resultado

def test_text_search_case_insensitive(tmp_path):
    archivo = tmp_path / "log.txt"
    archivo.write_text("Error grave\ntodo bien", encoding="utf-8")
    resultado = text_search(str(archivo), "error")
    assert "Línea 1" in resultado

def test_text_search_sin_coincidencias(tmp_path):
    archivo = tmp_path / "log.txt"
    archivo.write_text("todo bien", encoding="utf-8")
    resultado = text_search(str(archivo), "ERROR")
    assert "No se encontraron" in resultado

def test_text_search_termino_vacio(tmp_path):
    # Término vacío coincide con todas las líneas — limitación conocida
    archivo = tmp_path / "log.txt"
    archivo.write_text("linea 1\nlinea 2\nlinea 3", encoding="utf-8")
    resultado = text_search(str(archivo), "")
    assert "3 coincidencia(s)" in resultado

def test_text_search_no_encontrado():
    resultado = text_search("/ruta/inexistente.txt", "algo")
    assert "Error" in resultado


# ---------------------------------------------------------------------------
# agente — casos borde
# ---------------------------------------------------------------------------

def test_agente_answer_cuando_content_es_none():
    # Algunos LLMs reales devuelven content=None cuando no hay texto (solo tool_calls
    # en un turno previo). Si el LLM final devuelve content=None sin tool_calls,
    # el agente no debe romper — devuelve AgentResult válido.
    mock = MockLLMClient([LLMResponse(content=None, tool_calls=[])])
    agent = build_agent({"llm_client": mock})
    result = agent.run("hola")
    assert result is not None

def test_agente_max_iterations_cero():
    # Con max_iterations=0 el bucle no ejecuta nunca — devuelve AgentResult vacío
    # sin llamar al LLM ni una vez.
    # Nota: build_agent no expone max_iterations como config, por eso instanciamos
    # MyAgent directamente en este test.
    from student_framework.agent import MyAgent
    agent = MyAgent(llm_client=MockLLMClient([]), max_iterations=0)
    result = agent.run("¿cuánto es 2+2?")
    assert result.answer == ""
    assert result.steps == []

def test_agente_mensaje_vacio():
    mock = MockLLMClient([LLMResponse(content="No sé qué decir.")])
    agent = build_agent({"llm_client": mock})
    result = agent.run("")
    assert isinstance(result.answer, str)
