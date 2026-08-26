# Revision cualitativa M3

Esta dimension complementa las metricas cuantitativas del runner. La meta no
es medir solamente si el objetivo se cumplio, sino evaluar la calidad de la
trayectoria del agente: si explora con criterio, usa ids correctos, recuerda
estado, corrige errores y evita loops.

## Rubrica manual

Escala 0-3 por escenario:

- 0: no progresa. No obtiene informacion util, falla por error de runner o se
  queda sin acciones relevantes.
- 1: progresa poco. Observa parte del mundo, pero se atasca en loops,
  repite errores, inventa ids o no corrige acciones fallidas.
- 2: progreso parcial. Entiende objetos, salas o subobjetivos importantes,
  pero falla por orden, memoria, navegacion, inventario o combinacion.
- 3: resuelve con trayectoria aceptable. Completa el objetivo con un plan
  coherente, corrige errores locales y no presenta repeticiones graves.

## Criterios observables

Para asignar el puntaje, revisar `results.jsonl` y mirar:

- Uso de ids exactos: copia ids devueltos por las tools y no inventa aliases.
- Manejo de inventario: toma items revelados antes de usarlos o irse.
- Navegacion: usa salidas validas y vuelve a salas relevantes cuando hace falta.
- Memoria de objetivo: vuelve al objetivo principal cuando ya tiene piezas/llaves.
- Recuperacion de errores: cambia de estrategia despues de un error.
- Eficiencia: evita `look`, `examine`, `go` o `use` repetidos sin cambio de estado.

## Procedimiento automatico

Ejecutar:

```powershell
.\.venv\Scripts\python.exe .\eval\qualitative.py --results-dir eval\results\latest
```

El script lee `results.jsonl` y escribe:

- `qualitative_review.json`
- `qualitative_review.md`

La rubrica es heuristica y reproducible: asigna puntaje usando exito del
objetivo, errores de runner, progreso observable, repeticiones, errores de
herramientas y agotamiento de iteraciones.

## Procedimiento manual opcional

1. Correr una evaluacion valida sin errores de credenciales o runner.
2. Abrir `eval/results/latest/results.jsonl`.
3. Para cada escenario, asignar `qualitative_score` usando la rubrica.
4. Justificar cada puntaje con 1 o 2 observaciones concretas de la traza.
5. Reportar promedio general y ejemplos representativos en el informe.

## Tabla de revision

Completar esta tabla sobre una corrida final valida:

| Escenario | Dificultad | Score 0-3 | Justificacion breve |
| --- | --- | ---: | --- |
| study-with-key | easy | TBD | TBD |
| color-locks | medium | TBD | TBD |
| apartment-keys | medium | TBD | TBD |
| library-search | hard | TBD | TBD |
| office-sequence | hard | TBD | TBD |
| extreme-archive | extreme | TBD | TBD |
| vault-combination | extreme | TBD | TBD |
| backtracking-vault | extreme | TBD | TBD |

## Nota sobre la ultima corrida local

La corrida actual en `eval/results/latest` no debe usarse como evidencia final
si contiene `ExpiredTokenException` de AWS. Esos casos son fallos del runner o
credenciales, no fallos cualitativos del agente. Para el informe, usar una
corrida completa y valida, sin `runner_error`.
