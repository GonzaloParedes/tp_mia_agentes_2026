# STEPS - Milestone 3

Este documento deja el paso a paso para completar M3 desde el estado actual del repositorio.

Estado observado al iniciar:

- Branch actual: `m3-eval`.
- El agente de M1/M2 ya existe en `student_framework/agent.py`.
- Las tools propias registradas son `calculator`, `file_reader` y `text_search`.
- `ENUNCIADO_M3.md` esta presente pero sin trackear.
- Falta el scaffold de M3 esperado por el enunciado: no existen `mia_world/` ni `scenarios/`.
- Falta `ENUNCIADO_M2.md`, aunque existe `Informe_Milestone_2.docx`.
- `python -m pytest` no corre todavia porque faltan dependencias (`boto3`) y el paquete `mia_world`.

## 1. Preparar entorno reproducible

1. Crear y activar un entorno virtual desde la raiz del repo.

   En PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

   En Bash/WSL:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
2. Test manual de entorno:

   ```bash
   python --version
   python -c "import boto3, ollama, pydantic, pytest; print('deps ok')"
   ```
3. Ejecutar tests que no dependen de M3.

   ```bash
   python -m pytest tests/conformance/test_m1.py tests/conformance/test_m2.py tests/test_tool_schema.py tests/test_student_tools.py
   ```

   Criterio de aceptacion: todos pasan. Si fallan, corregir M1/M2 antes de tocar M3.

## 2. Restaurar o incorporar el scaffold de M3

El enunciado y los tests esperan estos paths:

- `mia_world/`
- `scenarios/`
- `mia_world/cli.py`
- `mia_world/tools.py`
- `mia_world/scenarios.py`
- `mia_world/goals.py`

1. Traer esos archivos desde la entrega docente, branch correcta o paquete original del TP.
2. Verificar que existen:

   ```bash
   python -c "import mia_world; print('mia_world ok')"
   python -m mia_world.cli list
   ```
3. Ejecutar los tests del mundo:

   ```bash
   python -m pytest tests/conformance/test_m3_world.py
   ```

   Criterio de aceptacion: pasan todos los tests de mundo. No modificar tests ni archivos marcados como FIJO salvo que el docente lo indique.
4. Test manual rapido del mundo:

   ```bash
   python -m mia_world.cli run --scenario easy
   ```

   Criterio de aceptacion: el runner carga el escenario y registra las tools del mundo. Si falla por falta de LLM, al menos debe quedar claro que el import y la resolucion del escenario funcionan.

## 3. Hacer que el agente sea usable para M3

1. Revisar si el system prompt actual alcanza para sala de escape.

   Archivo: `student_framework/agent.py`.

   Riesgo actual: el prompt esta orientado a las tools de M1 (`calculator`, `file_reader`, `text_search`) y no menciona `look`, `examine`, `take`, `use` ni `go`. Para M3 conviene especializarlo o permitir configurarlo por `build_agent(config)`.
2. Agregar soporte de configuracion sin romper M1/M2:

   - permitir `config["system_prompt"]`;
   - permitir `config["max_iterations"]`;
   - conservar defaults actuales.
3. Crear un prompt M3 para el runner de evaluacion. Debe indicar:

   - empezar con `look` salvo que ya tenga informacion suficiente;
   - examinar contenedores y objetos sospechosos;
   - tomar items utiles;
   - usar llaves/piezas sobre cerraduras;
   - en multi-sala, recordar mapa, salidas, habitacion actual e inventario;
   - para goals ordenados, obtener documentos/objetos requeridos antes de abrir la puerta;
   - no repetir indefinidamente la misma accion fallida.
4. Test manual con un mock o con LLM real:

   ```bash
   python -m mia_world.cli run --scenario easy
   ```

   Criterio de aceptacion: en `easy`, el agente deberia resolver en una secuencia parecida a `examine alfombra`, `take llave_oro`, `use llave_oro puerta_principal`.

## 4. Crear infraestructura de evaluacion reproducible

Crear `eval/run.py` como entrada obligatoria.

Responsabilidades minimas:

1. Descubrir escenarios en `scenarios/`.
2. Para cada escenario:

   - cargar el escenario con `mia_world.load_scenario`;
   - construir el mundo inicial;
   - construir el agente;
   - registrar `make_world_tools(world)`;
   - ejecutar `agent.run(scenario.user_message)`;
   - evaluar `check_goal(world, scenario.goal)`;
   - capturar `AgentResult.answer`, `steps`, errores, tokens, duracion y estado final relevante.
3. Persistir artefactos:

   - `eval/results/latest/results.jsonl`, una linea por escenario;
   - `eval/results/latest/summary.json`, resumen agregado;
   - opcional: `eval/results/latest/transcripts/`, un JSON por escenario.
4. Opciones utiles de CLI:

   ```bash
   python eval/run.py
   python eval/run.py --scenario easy
   python eval/run.py --scenario study-with-key
   python eval/run.py --max-iterations 30
   python eval/run.py --experiment baseline
   ```
5. Tests manuales:

   ```bash
   python eval/run.py --scenario easy
   python eval/run.py --scenario medium
   python eval/run.py
   ```

   Criterio de aceptacion:

   - los comandos terminan sin pasos manuales;
   - se escriben `results.jsonl` y `summary.json`;
   - cada fila tiene `scenario_id`, `difficulty`, `success`, `reason`, `tool_calls`, `duration_seconds`, `input_tokens`, `output_tokens`, `error`.

## 5. Definir metricas

Metricas cuantitativas recomendadas:

- `success_rate`: escenarios resueltos / total.
- `success_rate_by_difficulty`: desglose por `easy`, `medium`, `hard`, `extreme`.
- `tool_calls`: cantidad de llamadas reales a tools.
- `optimality_ratio`: `tool_calls / optimal_calls`, usando la tabla del enunciado.
- `latency_seconds`: duracion por escenario.
- `token_usage`: `input_tokens + output_tokens` si el proveedor lo reporta.

Dimension cualitativa recomendada:

- Rubrica manual de trayectoria, escala 0-3:
  - 0: no explora ni progresa.
  - 1: explora algo pero se atasca o repite acciones.
  - 2: resuelve parcialmente; entiende objetos/salas pero falla orden, memoria o combinacion.
  - 3: resuelve con plan coherente y sin repeticiones importantes.

Test manual:

1. Abrir `eval/results/latest/results.jsonl`.
2. Elegir un caso fallido y uno exitoso.
3. Asignar la rubrica en un campo `qualitative_score` o en una tabla separada.
4. Verificar que el informe pueda citar esos casos.

## 6. Implementar analisis de errores

Agregar clasificacion automatica inicial en `eval/run.py` o en `eval/analyze.py`.

Categorias sugeridas:

- `tool_error`: una tool devolvio `Error`.
- `unknown_tool`: el LLM pidio una tool inexistente.
- `max_iterations`: el agente corto por limite.
- `navigation_error`: uso incorrecto de `go` o no volvio a la sala necesaria.
- `missed_hidden_item`: no examino el contenedor correcto.
- `wrong_order`: abrio la puerta antes de cumplir un goal de secuencia.
- `context_loss`: repite acciones o contradice inventario/mapa.
- `not_solved_no_error`: no hubo error claro, pero `check_goal` fallo.

Test manual:

```bash
python eval/run.py --scenario hard --max-iterations 5
```

Criterio de aceptacion: debe producir algun fallo clasificado, probablemente `max_iterations`, sin romper el runner.

## 7. Ejecutar al menos dos experimentos

Experimento A: baseline M3.

- Prompt M3.
- `max_iterations` suficiente, por ejemplo 30 o 40.
- Todas las tools del mundo disponibles.

Comando:

```bash
python eval/run.py --experiment baseline --max-iterations 40
```

Experimento B: menos pasos.

- Mismo prompt.
- `max_iterations` reducido, por ejemplo 6 o 10.
- Esperado: mejora costo/latencia pero baja success en medium/hard/extreme.

Comando:

```bash
python eval/run.py --experiment max_steps_10 --max-iterations 10
```

Experimento C opcional: sin prompt especializado.

- Usar el prompt general de M2.
- Esperado: peor uso de `look`/`go`, mas repeticiones o fallos por no planificar.

Comando:

```bash
python eval/run.py --experiment generic_prompt --prompt generic
```

Experimento D opcional: sin memoria larga o ventana chica.

- `max_history_messages` bajo.
- Esperado: fallos en escenarios multi-sala o backtracking.

Comando:

```bash
python eval/run.py --experiment small_memory --max-history-messages 8
```

Criterio de aceptacion general: cada experimento genera una carpeta propia bajo `eval/results/` y el resumen permite comparar contra baseline.

## 8. Validar con escenarios deterministas

Los tests M3 ya incluyen secuencias optimas. Usarlas como oraculo para depurar el mundo y para comparar el agente.

Secuencias clave:

- `study-with-key`: `examine alfombra`, `take llave_oro`, `use llave_oro puerta_principal`.
- `color-locks`: cadena plata -> roja -> verde -> oro -> puerta.
- `apartment-keys`: navegar norte/este, tomar llave, volver oeste/sur, abrir puerta.
- `office-sequence`: obtener `documento_confidencial` antes de abrir `puerta_principal`.
- `extreme-archive`: encontrar `expediente_7240`, tomar `llave_archivo`, abrir puerta.
- `vault-combination`: recolectar `nucleo_rojo`, `nucleo_azul`, `nucleo_verde` y usarlos en la puerta.
- `backtracking-vault`: avanzar hasta la llave final, volver al cofre inicial y recien abrir la puerta.

Test manual:

```bash
python -m pytest tests/conformance/test_m3_world.py
```

Criterio de aceptacion: el mundo acepta todas esas soluciones optimas.

## 9. Escribir el informe obligatorio

Crear un informe M3, por ejemplo `Informe_Milestone_3.md`.

Estructura requerida:

1. Aproximacion:

   - como se reutiliza M1/M2;
   - que se especializo para M3;
   - como se registran las tools del mundo.
2. Metricas:

   - success rate;
   - tool calls / optimalidad;
   - latencia/tokens si estan disponibles;
   - rubrica cualitativa.
3. Resultados:

   - tabla por escenario;
   - tabla por dificultad;
   - resumen global.
4. Experimentos:

   - baseline vs `max_steps_10`;
   - baseline vs prompt generico o memoria chica;
   - conclusion concreta de cada comparacion.
5. Limitaciones y proximos pasos:

   - dependencia del LLM real;
   - sensibilidad a prompts;
   - perdida de mapa con ventana chica;
   - mejoras posibles: planner explicito, memoria estructurada de mapa/inventario, recuperacion para documentos largos.

Test manual:

1. Abrir `eval/results/latest/summary.json`.
2. Verificar que todos los numeros citados en el informe salen de artefactos reproducibles.
3. Re-ejecutar `python eval/run.py` y confirmar que el informe no depende de pasos manuales ocultos.

## 10. Checklist final antes de merge/tag

1. Ver estado:

   ```bash
   git status --short --branch
   ```
2. Correr tests automaticos:

   ```bash
   python -m pytest
   ```
3. Correr evaluacion M3:

   ```bash
   python eval/run.py
   ```
4. Revisar artefactos:

   - `eval/results/latest/results.jsonl`
   - `eval/results/latest/summary.json`
   - `Informe_Milestone_3.md`
5. Confirmar que no se suben secretos:

   ```bash
   git status --short
   git diff --stat
   ```
6. Commit:

   ```bash
   git add ENUNCIADO_M3.md STEPS.md eval Informe_Milestone_3.md
   git add mia_world scenarios
   git commit -m "Implementa evaluacion de Milestone 3"
   ```
7. Merge a `main` y tag:

   ```bash
   git checkout main
   git pull origin main
   git merge m3-eval
   git tag M3
   git push origin main
   git push origin M3
   ```
