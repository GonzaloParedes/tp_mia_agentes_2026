# Evaluacion cualitativa para la reentrega M3

Se aplico la rubrica automatica existente a las dos corridas completas, sin nuevas llamadas al LLM y sin modificar las reglas de puntuacion. Se amplio el reporte para conservar variante y repeticion, mostrar los contadores que apoyan el puntaje y agrupar resultados por variante. Cada JSON cualitativo incluye el hash del archivo de resultados utilizado.

## Datos y procedimiento reproducible

- Iteraciones: `20260909T035926Z-38168abc`, 96 casos.
- Memoria: `20260909T032652Z-733d4b97`, 48 casos.
- Ambas corridas usan Nova Lite, temperatura 0.2, `04_PROMPT`, historial de 80 mensajes, sin revision de finalizacion ni parada asistida. La primera varia el limite con memoria activa; la segunda varia memoria con limite 45.

```powershell
python -m eval.qualitative --results-dir eval/results/iterations/20260909T035926Z-38168abc
python -m eval.qualitative --results-dir eval/results/memory/20260909T032652Z-733d4b97
```

Cada comando lee `results.jsonl` y genera `qualitative_review.json` y `qualitative_review.md` en esa misma carpeta. La identidad de un caso es corrida + variante + escenario + repeticion. Los numeros de pasos indicados abajo comienzan en 1. Las trazas originales permanecen intactas.

El flujo es: configuracion → ejecucion del agente → herramientas y cambios del mundo → `check_goal` externo → registro por caso → rubrica sobre la traza → lectura razonada de ejemplos. El exito cuantitativo depende del mundo; el puntaje cualitativo caracteriza el recorrido con heuristicas y tambien utiliza ese exito. No es una medicion independiente de accuracy ni un LLM-as-judge.

## Como se puntua

| Puntaje | Interpretacion general                                                               |
| ------: | ------------------------------------------------------------------------------------ |
|       0 | Sin progreso detectable o sin trayectoria evaluable.                                 |
|       1 | Exploracion o progreso limitado, insuficiente.                                       |
|       2 | Subobjetivos completados sin resolver, o exito con errores/repeticiones importantes. |
|       3 | Objetivo resuelto con trayectoria coherente segun las reglas.                        |

Las reglas concretas en `eval/qualitative.py` son:

- Sin pasos o con error de runner: 0. No hubo errores de runner en las dos corridas seleccionadas.
- Si resuelve: 2 cuando hay al menos 3 repeticiones consecutivas, 8 llamadas repetidas o acciones posteriores al objetivo; tambien 2 con al menos 4 errores de herramientas o 4 llamadas repetidas. En otro caso: 3.
- Si no resuelve y no detecta progreso: 0. Con progreso: 2 si detecta alguna apertura o al menos dos recogidas; de lo contrario: 1. Los mensajes explicativos distinguen agotamiento/repeticiones de otros casos.

La repeticion se compara por nombre de herramienta y argumentos JSON como texto, sin considerar cambios de estado. El progreso se detecta por expresiones como `Tomas`, `Llegas a`, `Contiene` o `se abre`. Estas decisiones permiten automatizar, pero pueden producir falsos positivos.

## Resultados automaticos (escala 0-3)

| Experimento | Variante    | Casos | Promedio |
| ----------- | ----------- | ----: | -------: |
| Iteraciones | 15          |    24 |    2.083 |
| Iteraciones | 30          |    24 |    2.375 |
| Iteraciones | 45          |    24 |    2.125 |
| Iteraciones | 60          |    24 |    2.375 |
| Memoria     | Sin memoria |    24 |    2.208 |
| Memoria     | Con memoria |    24 |    2.375 |

La tasa de exito crece con el limite en el experimento de iteraciones, pero el puntaje de trayectoria no crece de forma monotona. Con memoria, el promedio cualitativo y el exito agregado mejoran en esta corrida. Son promedios de una escala ordinal heuristica sobre ocho escenarios y tres repeticiones, no pruebas de significacion estadistica.

## Tres ejemplos para explicar el proceso

Seleccion intencional de tres comportamientos contrastantes, no una muestra aleatoria ni una validacion exhaustiva. La lectura razonada siguiente fue preparada con asistencia de Codex; el grupo debe revisarla antes de incorporarla como evaluacion humana en el informe.

### 1. Resolucion eficiente

Caso: corrida de iteraciones, `iterations_15`, `study-with-key`, repeticion 1.

| Paso | Accion                               | Evidencia                                      |
| ---: | ------------------------------------ | ---------------------------------------------- |
|    1 | `look()`                           | Observa alfombra, escritorio y puerta.         |
|    2 | `examine(alfombra)`                | Revela`llave_oro`.                           |
|    3 | `take(llave_oro)`                  | Confirma que toma la llave.                    |
|    4 | `use(llave_oro, puerta_principal)` | La herramienta confirma que la puerta se abre. |

`goal_achieved=true`, sin errores ni llamadas repetidas. Responde con texto y no ejecuta mas herramientas. Puntaje automatico **3**; lectura razonada **3**, de acuerdo: observa, revela, recoge y usa sin desvio. La respuesta incluye etiquetas `<thinking>`, un problema de presentacion que esta rubrica de trayectoria no penaliza.

### 2. Atasco pese a tener una accion util disponible

Caso: corrida de memoria, `with_memory`, `color-locks`, repeticion 2.

En el paso 6 intenta usar `llave_plata` sin inventario; la memoria lo bloquea. En el 7 la recoge y en el 8 la prueba contra la puerta principal: no encaja. Los pasos 9–45 vuelven a inspeccionar los cofres; nunca usa la llave plateada sobre el cofre plateado. Termina sin abrir la puerta, con 45 intentos, 38 llamadas repetidas y un error de herramienta.

Puntaje automatico **2**; lectura razonada propuesta **1**: hay exploracion y una recogida, pero no resuelve la cadena de cerraduras y queda atascado. La diferencia revela un defecto de la heuristica: `_count_openings` busca `se abre` en cualquier salida, y las descripciones de `cofre_azul` contienen «las bisagras se abren al primer empujon». La rubrica lo interpreta como apertura aunque provenga de una descripcion repetida por `examine`, no de una nueva accion exitosa. Se conserva el 2 automatico en los resultados y se explicita el desacuerdo; no se corrige retrospectivamente para mejorar los numeros.

### 3. Objetivo cumplido, finalizacion incorrecta

Caso: corrida de iteraciones, `iterations_60`, `office-sequence`, repeticion 2.

- Paso 14: recoge `documento_confidencial`.
- Paso 15: recoge `llave_maestra`.
- Paso 20: abre `puerta_principal`. La reproduccion de la traza confirma que `check_goal` ya cumple la secuencia requerida.
- Pasos 21-61: agrega **41 acciones**; insiste con direcciones invalidas y recorre salas.
- Final: agota iteraciones y devuelve «No se pudo completar la tarea dentro del limite de iteraciones configurado», pese a que el mundo confirma exito.

Puntaje automatico **2**; lectura razonada **2** para la trayectoria: resolvio los subobjetivos, pero con repeticion y sobrecosto. Hay 13 errores de herramientas, 47 llamadas repetidas y 5 repeticiones consecutivas. Por separado, la respuesta final es incorrecta respecto del estado logrado. Este caso explica por que accuracy del mundo no basta para caracterizar el comportamiento del agente.

## Limitaciones y texto sugerido para el informe

La rubrica mezcla exito y eficiencia, no verifica directamente la veracidad de la respuesta final y puede confundir descripciones con progreso. Repetir un `go` puede ser necesario para volver por un camino, mientras que comparar argumentos como texto puede omitir repeticiones semanticamente identicas. La categoria de acciones posteriores al objetivo se basa en la apertura de la puerta principal; en el ejemplo ordenado se verifico adicionalmente la secuencia completa. Los resultados automaticos requieren interpretacion, no deben usarse como juez definitivo.

> Complementamos el exito sobre el estado del mundo con una rubrica automatica de trayectoria de 0 a 3. Registramos variantes, repeticiones y evidencia de errores y repeticiones, y analizamos tres casos contrastantes. El analisis muestra que cumplir el objetivo no implica finalizar correctamente: algunas ejecuciones siguen actuando y terminan con una respuesta de fracaso. Tambien detectamos un falso positivo de progreso en la rubrica, por lo que presentamos sus puntajes como indicadores heurísticos y explicitamos sus limitaciones.

Antes de la entrega: el grupo debe validar los tres ejemplos, incorporar las tablas y graficos cuantitativos y distinguir la lectura propia de este borrador asistido. Si se modifica la rubrica, asignarle otra version y recalcular todas las variantes, sin mezclar puntajes de versiones distintas.
