# Evaluacion de experimentos

Cada JSON activo define una pregunta experimental, sus escenarios, repeticiones y variantes. La configuracion se resuelve antes de ejecutar. Las variantes heredan `defaults` y solo declaran los valores que cambian.

| Plan | Comparacion | Casos con la configuracion incluida |
| --- | --- | ---: |
| `iterations.json` | 15, 30, 45 y 60 iteraciones, con memoria | 96 |
| `memory.json` | Memoria activada/desactivada, 45 iteraciones | 48 |
| `prompts.json` | Prompt 03/04, con memoria, 45 iteraciones | 48 |

Todos usan los ocho escenarios y tres repeticiones. Una iteracion es una llamada al LLM; puede incluir varias herramientas. Las metricas actuales cuentan herramientas, no iteraciones efectivamente consumidas.

`stop_on_goal` esta desactivado en todos los planes actuales y por defecto. La comprobacion externa queda disponible solo como variante asistida explicita. Los resultados anteriores se conservan con la configuracion que realmente utilizaron.

El piloto compara `use_completion_review: false` y `true` en `color-locks` y `office-sequence`, con tres repeticiones: **12 casos**. Ambas variantes usan memoria y `stop_on_goal: false`. Para validarlo y ejecutarlo:

```powershell
python -m eval.run --experiments experiments/pilot.json --dry-run
python -m eval.run --experiments experiments/pilot.json
```

La revision observacional agrega al contexto el pedido original y las ultimas 12 acciones `take`/`use` con sus resultados (hasta 600 caracteres por resultado), en orden, incluyendo fallos. El modelo decide si seguir o terminar. La primera respuesta de texto puede reconsiderarse una sola vez, si queda presupuesto; esa llamada cuenta dentro de `max_iterations` y sus tokens se suman normalmente. No usa `check_goal`, ni obtiene datos privados del mundo, ni garantiza que el modelo reconozca el exito. El limite de mensajes sigue vigente; este contexto adicional en el system prompt tiene un coste que debe medirse.

`use_completion_review` y `completion_reviews` quedan registrados en cada resultado. El manifest y el reporte identifican la variante; `termination_reason` sigue distinguiendo respuesta del modelo, agotamiento de iteraciones y parada asistida. No se activa todavia en los planes de iteraciones/memoria/prompts hasta evaluar el piloto.

## Comandos

Desde la raiz del repositorio, con el entorno Python activado:

```powershell
# Validar configuracion, prompts y escenarios; no consume tokens ni crea resultados.
python -m eval.run --experiments experiments/iterations.json --dry-run

# Ejecutar con el proveedor configurado en el entorno.
python -m eval.run --experiments experiments/iterations.json
python -m eval.run --experiments experiments/memory.json
python -m eval.run --experiments experiments/prompts.json

# Regenerar resumen y graficos desde resultados guardados, sin llamar al LLM.
python -m eval.run --report eval/results/iterations/<identificador>

# Rubrica cualitativa existente sobre todas las trazas de una corrida.
python -m eval.qualitative --results-dir eval/results/iterations/<identificador>
```

Tambien funciona `python eval/run.py --experiments ...`. La consola muestra progreso y la ruta final; el JSON completo queda en archivos.

## Configuracion

```json
{
  "name": "pilot",
  "scenarios": ["vault-combination"],
  "repetitions": 1,
  "defaults": {
    "prompt": "prompts/04_PROMPT",
    "max_iterations": 45,
    "max_history_messages": 80,
    "use_structured_memory": true
  },
  "variants": [
    {"id": "without_memory", "use_structured_memory": false},
    {"id": "with_memory", "use_structured_memory": true}
  ]
}
```

Guardar el ejemplo como otro JSON permite hacer un piloto antes de la evaluacion completa. `scenarios` acepta `"all"` o una lista de ids exactos. Las rutas de prompts y las rutas relativas de CLI se resuelven desde la raiz del repositorio. Los booleanos deben ser JSON `true`/`false`; se rechazan campos desconocidos, ids duplicados, limites invalidos y overrides `null`. Omitir un campo de una variante significa heredar el default.

Los parametros experimentales viven en el JSON: se eliminaron los flags `--runs`, `--scenario`, `--prompt`, `--max-iterations`, `--max-history-messages` y `--use-structured-memory` del evaluador. Para cambiar esas condiciones, editar/copiar el plan. `mia_world.cli` sigue disponible para ejecuciones individuales del mundo.

## Resultados

Cada invocacion crea una carpeta nueva; no se reutilizan carpetas ni se sobrescriben corridas:

```text
eval/results/<nombre>/<fecha-UTC>-<id>/
  manifest.json
  results.jsonl
  scenarios/          # Copias exactas del dataset utilizado
  summary.json
  report.md
  comparison.svg
```

- `manifest.json`: configuracion resuelta, texto exacto de cada prompt, escenarios, proveedor/modelo del entorno, temperatura del cliente estandar, commit, cambios locales y hashes del codigo. No guarda credenciales. Con `--module` personalizado, revisar si el modulo utiliza otro cliente o temperatura.
- `results.jsonl`: una linea por variante, repeticion y escenario, con resultado, herramientas, errores y tokens. Se guarda y sincroniza a disco al terminar cada caso.
- `summary.json`: agregados por variante, escenario y repeticion, calculados siempre desde los resultados originales.
- `report.md` y `comparison.svg`: tabla y graficos para revisar los resultados.

El orden es repeticion ? variante ? escenario. Cada caso carga un mundo nuevo y construye un agente nuevo. La estructura no cambia cuando hay una sola repeticion.

Una interrupcion controlada deja el manifest con estado `interrupted` y reportes parciales. Un cierre abrupto puede dejar estado `running`; `--report` recupera los casos completos e ignora una ultima linea JSON truncada. Se muestra cuantos casos se guardaron sobre cuantos estaban previstos. No hay reanudacion automatica: otra ejecucion crea otra carpeta. Solo se garantiza conservar casos terminados; una excepcion del agente puede seguir perdiendo su traza parcial.

Los errores de ejecucion cuentan como fallos en las metricas actuales; los tokens no reportados suman cero. Las categorias de repeticion son heuristicas. Esta refactorizacion conserva esos criterios para no mezclar cambios de almacenamiento con cambios de evaluacion.

`--output-root` permite elegir otra raiz de resultados; `--scenarios-dir`, otro dataset. Codigo de salida: 0 si todos los casos cumplen el objetivo sin errores, 1 si hay fallos, 2 si la configuracion es invalida.

## Experimentos historicos

Los siete archivos numerados anteriores estan en `archive/`, sin modificar su contenido. Conservan el contexto de la bitacora; su formato de lista ya no se ejecuta con el nuevo runner. Las rutas `results_dir` por variante se eliminaron del formato activo para evitar colisiones. Los resultados antiguos permanecen en sus carpetas y no se migran ni se sobrescriben.

Las comparaciones historicas que pretendian desactivar memoria deben repetirse por el error de configuracion corregido previamente. Para una comparacion nueva, mantener modelo, temperatura y codigo constantes durante toda la corrida.
