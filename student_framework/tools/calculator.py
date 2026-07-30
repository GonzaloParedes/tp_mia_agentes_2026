from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from mia_agents.types import ToolSchema


def _coerce_numeric(value: object) -> tuple[float | int | None, str | None]:
    """Convierte `value` a int o float. Devuelve (número, None) o (None, motivo)."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value, None
    if isinstance(value, str):
        # Probar int primero: si "3" fuera directo a float, calculator(3,4,"+")
        # devolvería "7.0" en vez de "7", cambiando el formato de salida ya
        # esperado por los tests existentes.
        try:
            return int(value), None
        except ValueError:
            pass
        try:
            return float(value), None
        except ValueError:
            pass
    return None, f"no se puede interpretar como número: {value!r} (tipo {type(value).__name__})"


def calculator(
    a: Annotated[float, Field(description="El primer numero.")],
    b: Annotated[float, Field(description="El segundo numero.")],
    operator: Annotated[
        Literal["+", "-", "*", "%"],
        Field(description="El operador a aplicar: +, -, * o % (modulo)."),
    ],
) -> str:
    """Hace la operacion matematica entre dos numeros y devuelve el resultado."""
    # El LLM arma los argumentos como JSON crudo: puede mandar un operando
    # no numérico o un operador fuera del Literal (el schema es una guía
    # para el LLM, no una validación en runtime — la anotación `a: float`
    # no convierte nada por sí sola). Se valida y CONVIERTE acá, y de ahí
    # en más se opera con el valor ya convertido, no con el original.
    a, error_a = _coerce_numeric(a)
    if error_a:
        return f"Error: el parámetro 'a' es inválido: {error_a}."
    b, error_b = _coerce_numeric(b)
    if error_b:
        return f"Error: el parámetro 'b' es inválido: {error_b}."

    if operator not in ("+", "-", "*", "%"):
        return (
            f"Error: operador '{operator}' no soportado. "
            "Los operadores permitidos son: +, -, * y % (módulo)."
        )

    if operator == "+":
        return str(a + b)
    if operator == "-":
        return str(a - b)
    if operator == "*":
        return str(a * b)
    # A esta altura operator == "%": único caso que puede fallar
    # (los demás nunca fallan entre operandos numéricos).
    try:
        return str(a % b)
    except ZeroDivisionError:
        return (
            "Error: no se puede calcular el módulo con divisor 0 (b=0); "
            "el segundo operando debe ser distinto de cero."
        )

calculator_schema = ToolSchema.from_callable(calculator)