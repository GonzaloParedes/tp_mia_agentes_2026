# Experiments - M3

Carpeta para organizar las ablaciones y variantes de evaluacion de M3.

La fuente de verdad es `experiments/experiments.json`. `eval/run.py` puede
leer ese archivo y ejecutar todos los experimentos definidos ahi.

Los prompts viven en `prompts/`. Si un experimento tiene `"prompt": null`,
se usa el prompt default interno del agente.

Comando:

```powershell
.\.venv\Scripts\python.exe eval\run.py --experiments experiments\experiments.json
```

Cada corrida crea una carpeta nueva con timestamp:

```text
eval/results/experiments/YYYYMMDD-HHMMSS/
```

Dentro de esa carpeta quedan los resultados de cada experimento y la comparacion
agregada. Para elegir manualmente el directorio:

```powershell
.\.venv\Scripts\python.exe eval\run.py --experiments experiments\experiments.json --experiments-results-dir eval\results\experiments\mi-corrida
```

## Experimentos definidos

1. `01_default`: prompt y parametros default del agente.
2. `02_prompt`: variante con `prompts/02_PROMPT`.
3. `03_prompt`: variante con `prompts/03_PROMPT`.
4. `04_max_iterations`: variante modificando `max_iterations`.
5. `05_max_history`: variante modificando `max_history_messages`.

## Comparacion esperada

Despues de correrlos, comparar los `summary.json` de cada carpeta:

- `success_rate`
- `by_difficulty`
- `avg_tool_calls`
- `input_tokens` / `output_tokens`
- `error_categories`
- `failed_scenarios`

El runner tambien genera comparacion agregada en:

- `comparison.json`: tabla con las metricas principales por experimento.
- `comparison.svg`: imagen con 4 plots comparando tasa de exito, tool calls, tokens y errores.
