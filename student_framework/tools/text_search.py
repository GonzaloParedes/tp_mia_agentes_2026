from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mia_agents.types import ToolSchema
from student_framework.tools._sandbox import resolve_sandboxed_path


def text_search(
    file_path: Annotated[
        str,
        Field(
            description=(
                "Ruta relativa exacta proporcionada explícitamente por el usuario. "
                "No inventar archivos ni usar esta herramienta para buscar datos "
                "mencionados en la conversación."
            )
        ),
    ],
    search_term: Annotated[
        str,
        Field(
            description=(
                "Término o frase que el usuario pidió explícitamente buscar "
                "dentro del archivo indicado."
            )
        ),
    ],
) -> str:
    """Busca texto en un archivo cuando el usuario proporciona la ruta y lo pide.

    No usar para recordar o recuperar información mencionada en la conversación.
    """
    if not isinstance(search_term, str):
        # El schema sugiere "string" al LLM, pero no lo fuerza en runtime
        # (misma situación que los operandos de calculator): un JSON con
        # search_term como número rompería en .lower() más abajo si no
        # se valida acá.
        return (
            f"Error: el parámetro 'search_term' debe ser texto, recibí "
            f"{search_term!r} (tipo {type(search_term).__name__})."
        )

    path, error = resolve_sandboxed_path(file_path)
    if error:
        return error

    if path.is_dir():
        nombres = sorted(p.name for p in path.iterdir())
        listado = ", ".join(nombres) if nombres else "(está vacío)"
        return (
            f"Error: '{file_path}' es un directorio, no un archivo. "
            f"Contenido de ese directorio: {listado}."
        )

    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except FileNotFoundError:
        parent = path.parent
        if parent.is_dir():
            nombres = sorted(p.name for p in parent.iterdir())
            listado = ", ".join(nombres) if nombres else "(está vacío)"
            return (
                f"Error: no se encontró el archivo '{file_path}'. "
                f"Archivos disponibles en ese directorio: {listado}."
            )
        return f"Error: no se encontró el archivo '{file_path}'."
    except UnicodeDecodeError:
        return f"Error: '{file_path}' no es un archivo de texto UTF-8 válido."

    matches = []
    for i, line in enumerate(lines):
        if search_term.lower() in line.lower():
            matches.append(f"Línea {i + 1}: {line.rstrip()}")

    if not matches:
        return f"No se encontraron coincidencias para '{search_term}' en '{file_path}'."

    return f"{len(matches)} coincidencia(s) encontrada(s):\n" + "\n".join(matches)


text_search_schema = ToolSchema.from_callable(text_search)
