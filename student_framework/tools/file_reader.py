from __future__ import annotations

from typing import Annotated

from pydantic import Field

from mia_agents.types import ToolSchema


def file_reader(file_path: Annotated[str, Field(description="La ruta del archivo a leer.")]) -> str:
    """Lee el contenido del archivo indicado y devuelve el resultado."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: no se encontró el archivo '{file_path}'."
    except IsADirectoryError:
        return f"Error: '{file_path}' es un directorio, no un archivo."
    except UnicodeDecodeError:
        return f"Error: '{file_path}' no es un archivo de texto UTF-8 válido."


file_reader_schema = ToolSchema.from_callable(file_reader)