from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from mia_agents.types import ToolSchema


def calculator(
    a: Annotated[float, Field(description="El primer numero.")],
    b: Annotated[float, Field(description="El segundo numero.")],
    operator: Annotated[
        Literal["+", "-", "*", "%"],
        Field(description="El operador a aplicar: +, -, * o % (modulo)."),
    ],
) -> str:
    """Hace la operacion matematica entre dos numeros y devuelve el resultado."""
    try:
        if operator == "+":
            return str(a + b)
        elif operator == "-":
            return str(a - b)
        elif operator == "*":
            return str(a * b)
        elif operator == "%":
            return str(a % b)
        else:
            raise ValueError("Operador no valido.")
    except ZeroDivisionError as e:
        return "Error: No se puede dividir por cero."

calculator_schema = ToolSchema.from_callable(calculator)