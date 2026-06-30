from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mia_agents.types import ToolSchema


def text_search(
    file_path: Annotated[str, Field(description="La ruta del archivo de texto donde buscar.")],
    search_term: Annotated[str, Field(description="El término o frase a buscar en el archivo.")],
) -> str:
    """Busca un término en un archivo de texto y devuelve las líneas que lo contienen."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"Error: no se encontró el archivo '{file_path}'."
    except IsADirectoryError:
        return f"Error: '{file_path}' es un directorio, no un archivo."
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
