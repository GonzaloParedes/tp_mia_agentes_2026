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

Para repetir cada variante varias veces y reducir ruido del LLM:

```powershell
.\.venv\Scripts\python.exe eval\run.py --experiments experiments\04-structured-memory.json --runs 3
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

Experimento de memoria estructurada:

```powershell
.\.venv\Scripts\python.exe eval\run.py --experiments experiments\04-structured-memory.json --experiments-results-dir eval\results\experiments\structured-memory-active
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

Si se usa `--runs N`, cada experimento guarda sus repeticiones en:

```text
experimento/run_01/
experimento/run_02/
...
```

El `summary` del experimento agrega todas las repeticiones, y
`run_summaries` conserva el resultado de cada repeticion.

## Memoria estructurada

El campo `"use_structured_memory": true` activa una memoria estructurada del
agente. Esta memoria no reemplaza al LLM ni modifica el mundo: resume hechos
extraidos de las herramientas (`look`, `examine`, `take`, `use`, `go`), los
agrega al system prompt en cada iteracion y valida contradicciones fuertes
antes de ejecutar algunas herramientas.

La memoria registra sala actual, salidas conocidas, objetos vistos,
inventario observado, objetos revelados pero no tomados, objetos abiertos y
acciones fallidas recientes. La hipotesis del experimento es reducir errores
de inventario, navegacion y repeticion.

Guardrails activos iniciales:

- bloquear `go` cuando la direccion no existe desde la sala actual conocida;
- bloquear `use` cuando el item fue revelado pero no tomado, o no aparece en el inventario observado;
- bloquear `take`, `examine` o `use` sobre objetos conocidos en otra sala cuando la sala actual es distinta.
