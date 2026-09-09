"""Carga y validacion de planes de evaluacion, sin llamadas al LLM."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

ROOT_DIR = Path(__file__).resolve().parents[1]
SAFE_ID = r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$"


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT_DIR / path


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = "prompts/04_PROMPT"
    max_iterations: StrictInt = Field(default=45, ge=1)
    max_history_messages: StrictInt = Field(default=80, ge=1)
    use_structured_memory: StrictBool = True
    stop_on_goal: StrictBool = False
    use_completion_review: StrictBool = False


class Variant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=SAFE_ID)
    description: str = ""
    prompt: str | None = None
    max_iterations: StrictInt | None = Field(default=None, ge=1)
    max_history_messages: StrictInt | None = Field(default=None, ge=1)
    use_structured_memory: StrictBool | None = None
    stop_on_goal: StrictBool | None = None
    use_completion_review: StrictBool | None = None

    @model_validator(mode="after")
    def reject_explicit_null(self):
        for key in self.model_fields_set:
            if getattr(self, key) is None:
                raise ValueError(f"{key}: omitir el campo para heredar; null no esta permitido")
        return self


class ExperimentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(pattern=SAFE_ID)
    scenarios: list[str] | str = "all"
    repetitions: StrictInt = Field(default=3, ge=1)
    defaults: Settings = Field(default_factory=Settings)
    variants: list[Variant] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_selection(self):
        ids = [v.id for v in self.variants]
        if len(set(ids)) != len(ids):
            raise ValueError("Los ids de las variantes deben ser unicos")
        if self.scenarios != "all":
            if not isinstance(self.scenarios, list) or not self.scenarios:
                raise ValueError("scenarios debe ser 'all' o una lista no vacia de ids")
            if len(set(self.scenarios)) != len(self.scenarios):
                raise ValueError("Hay escenarios duplicados")
        return self

    def resolved_variants(self) -> list[dict]:
        resolved = []
        for variant in self.variants:
            overrides = variant.model_dump(exclude_unset=True, exclude={"id", "description"})
            settings = Settings.model_validate({**self.defaults.model_dump(), **overrides})
            data = settings.model_dump()
            prompt = repo_path(settings.prompt).read_text(encoding="utf-8").strip()
            if not prompt:
                raise ValueError(f"Prompt vacio: {settings.prompt}")
            resolved.append({"id": variant.id, "description": variant.description,
                             **data, "system_prompt": prompt})
        return resolved


def load_plan(path: str | Path) -> ExperimentPlan:
    data = json.loads(repo_path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        raise ValueError("Formato historico: usar un plan con name, scenarios, defaults y variants; ver experiments/README.md")
    return ExperimentPlan.model_validate(data)
