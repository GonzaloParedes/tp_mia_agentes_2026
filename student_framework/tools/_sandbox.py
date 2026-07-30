"""Validación de rutas compartida por las tools de I/O (file_reader, text_search).

Ambas tools solo pueden leer dentro de SANDBOX_ROOT. `resolve_sandboxed_path`
centraliza esa regla para no duplicarla entre las dos.
"""

from __future__ import annotations

import os
from pathlib import Path

# Carpeta raíz permitida para lectura. Nivel de módulo (no hardcodeada
# dentro de cada función) para que los tests puedan hacer
# monkeypatch.setattr(modulo, "SANDBOX_ROOT", tmp_path) sin tocar la firma
# de las tools, que solo reciben `file_path: str`.
SANDBOX_ROOT = (Path(__file__).resolve().parent.parent / "sandbox")


def resolve_sandboxed_path(file_path: str) -> tuple[Path | None, str | None]:
    """Valida `file_path` contra las reglas del sandbox.

    Devuelve (ruta_resuelta, None) si es válida, o (None, mensaje_de_error)
    si viola alguna regla. Exactamente uno de los dos es None.
    """
    if not file_path:
        return None, (
            "Error: la ruta no puede estar vacía. Debe ser una ruta relativa "
            "dentro del sandbox, por ejemplo 'ejemplo.txt' o 'datos/notas.txt'."
        )

    if os.path.isabs(file_path):
        return None, (
            f"Error: '{file_path}' es una ruta absoluta; no está permitido. "
            "Usá una ruta relativa a la raíz del sandbox, por ejemplo 'ejemplo.txt'."
        )

    if ".." in Path(file_path).parts:
        return None, (
            f"Error: '{file_path}' contiene '..'; no está permitido subir de "
            "directorio. Usá una ruta relativa que se quede dentro del sandbox."
        )

    sandbox_root = SANDBOX_ROOT.resolve()
    candidate = (sandbox_root / file_path).resolve()
    if sandbox_root not in candidate.parents and candidate != sandbox_root:
        return None, (
            f"Error: '{file_path}' resuelve fuera del sandbox permitido."
        )

    return candidate, None
