from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mia_agents.types import ToolSchema
from student_framework.tools._sandbox import resolve_sandboxed_path


def file_reader(
    file_path: Annotated[
        str,
        Field(
            description=(
                "Ruta relativa exacta proporcionada explícitamente por el usuario. "
                "No inventar ni completar rutas, y no usar esta herramienta para "
                "recordar datos de la conversación."
            )
        ),
    ],
) -> str:
    """Lee un archivo cuando el usuario pide explícitamente leer una ruta.

    No usar para recordar o recuperar información mencionada en la conversación.
    """
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
        return path.read_text(encoding="utf-8")
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


file_reader_schema = ToolSchema.from_callable(file_reader)
