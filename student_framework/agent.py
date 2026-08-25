"""Implementación de su agente.

Completen `register_tool` y `run` para el Milestone 1.
En el Milestone 2 amplíen `MyAgent` para que sea estatal y respete
`max_history_messages`.

Los tests de conformidad en `tests/conformance/test_m1.py` y
`test_m2.py` describen con precisión qué comportamientos deben funcionar
— léanlos antes de empezar.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from botocore.exceptions import ClientError
from ollama import ResponseError as OllamaResponseError
from pydantic import ValidationError

from mia_agents.protocols import LLMClient
from mia_agents.tool_schema import FINAL_RESULT_TOOL_NAME, final_result_tool_schema
from mia_agents.types import AgentResult, AgentStep, ToolSchema
from student_framework.world_memory import WorldMemory

# Códigos/status de ClientError (Bedrock/AWS) que sí vale la pena reintentar:
# throttling y errores de servidor. Cualquier otro ClientError (permisos,
# parámetros inválidos, modelo inexistente...) no se arregla reintentando.
_TRANSIENT_AWS_ERROR_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerException",
    "RequestTimeoutException",
}
_TRANSIENT_HTTP_STATUS = {429, 500, 502, 503, 504}


class StructuredOutputError(Exception):
    """Se agotaron los reintentos de `structured_call` sin una salida válida."""


class MyAgent:
    # Excepciones que consideramos SIEMPRE fallos transitorios de red/timeout
    # (independientes del proveedor) y por lo tanto reintentables sin
    # involucrar al LLM. Cualquier otra excepción se re-lanza en el primer
    # intento, salvo que _is_transient_client_error la reclasifique.
    _TRANSIENT_EXCEPTIONS = (TimeoutError, ConnectionError, OSError)

    @staticmethod
    def _is_transient_client_error(exc: BaseException) -> bool:
        """True si `exc` es un error del proveedor (Bedrock u Ollama) de
        throttling/servidor (5xx/429), independientemente de cuál de los
        dos esté configurado.

        Se mira el código de error / status HTTP en vez de reintentar
        cualquier excepción del proveedor: esas clases también cubren
        errores permanentes (credenciales, parámetros inválidos, modelo
        inexistente) que reintentar no arregla.
        """
        if isinstance(exc, ClientError):
            error = exc.response.get("Error", {})
            status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            return error.get("Code") in _TRANSIENT_AWS_ERROR_CODES or status in _TRANSIENT_HTTP_STATUS
        if isinstance(exc, OllamaResponseError):
            return exc.status_code in _TRANSIENT_HTTP_STATUS
        return False

    def __init__(
        self,
        llm_client: LLMClient,
        system_prompt: str = (
"""Sos un agente con herramientas. Respondes en espanol y resolves tareas paso a paso usando las herramientas disponibles.

Reglas generales:
- Usa herramientas cuando sean necesarias para observar, calcular, leer archivos o actuar sobre un entorno.
- Copia exactamente los ids, rutas y argumentos que devuelven las herramientas. No reemplaces ids por nombres visibles.
- Si una herramienta devuelve un error por id inexistente, usa `look` u otra observacion disponible para obtener el id correcto.
- No repitas la misma llamada si ya devolvio la misma informacion o el mismo error.
- Ante un error de herramienta, corregi la causa antes de intentar otra vez.
- Antes de usar una llave, pieza o item, verifica que este en el inventario segun las observaciones previas o la memoria estructurada. Si fue revelado pero no tomado, volve al lugar donde lo viste y usa `take` antes de intentar `use`.
- Si una observacion revela varios items utiles en un contenedor abierto, toma todos los items potencialmente utiles antes de irte de la sala.

Uso de memoria estructurada:
- Si el system prompt incluye una seccion llamada "Memoria estructurada observada del entorno", tratala como tu estado de trabajo confiable.
- Antes de cada tool call, revisa en la memoria: sala actual, inventario observado, objetos revelados pero no tomados, objetos conocidos en la sala actual, salidas conocidas, salidas bloqueadas, acciones fallidas recientes y siguiente objetivo sugerido.
- Dale prioridad a la memoria estructurada sobre tu intuicion. Si la memoria dice que un objeto fue visto en otra sala, navega primero a esa sala antes de `take`, `examine` o `use`.
- Si la memoria muestra objetos revelados pero no tomados, toma esos objetos antes de moverte.
- Si la memoria muestra salidas conocidas de la sala actual, usa solo esas direcciones con `go`.
- Si la memoria muestra acciones fallidas recientes, no repitas la misma accion; cambia de estrategia usando la informacion del error.
- Si aparece "Siguiente objetivo sugerido", seguilo salvo que contradiga una observacion mas reciente.

Para mundos tipo sala de escape:
- Empeza con `look` si no conoces el estado actual.
- `look` muestra objetos con formato `[id: ...]`; usa siempre esos ids exactos.
- Examina objetos selectivamente para entender contenedores, cerraduras, pistas u objetos sospechosos; no examines todo si ya hay una accion util evidente.
- Si ves un objeto tomable util, usa `take` con su id.
- Si tenes una llave o pieza y hay un contenedor, cerradura o bloqueo compatible por color, nombre o descripcion, proba `use(item, target)` antes de seguir explorando.
- Si un contenedor u objeto cerrado requiere una llave o pieza que todavia no tenes en el inventario, no intentes abrirlo: busca, revela y toma primero el item requerido.
- No sigas examinando el mismo contenedor cerrado si ya sabes que requiere una llave o pieza; abrilo primero cuando tengas el item compatible.
- Despues de abrir un contenedor, usa `examine` sobre ese contenedor para revelar su contenido.
- Despues de revelar un item util, tomalo con `take`.
- Despues de tomar una llave, pieza o item claramente util, preguntate si ayuda al objetivo principal o a un bloqueo ya visto. Si conoces donde esta ese objetivo o bloqueo, volve y proba el item compatible antes de explorar salas menos relevantes.
- Si una herramienta dice que a un objetivo le faltan piezas, items o condiciones, trata esos faltantes como subobjetivos prioritarios: busca, toma y lleva esos items de vuelta al objetivo.
- Recorda el objetivo principal. Si una tool confirma que el objetivo ya se cumplio, no uses mas herramientas y responde con la respuesta final.
- Si `use(item, "puerta_principal")` devuelve que la puerta se abre, termina inmediatamente con respuesta final. No llames `look`, `go`, `examine`, `take` ni `use` despues de eso.

Busqueda sistematica:
- Si examinas varios objetos similares y no encontras nada util, continua con el siguiente id pendiente de la lista revelada.
- No vuelvas a `look` salvo que hayas agotado la lista de objetos pendientes, cambiado de sala o cambiado el estado del mundo abriendo/tomando/usando algo.
- No llames `look` repetidamente en la misma sala si la observacion no cambio. Si no avanzaste, elegi un objeto pendiente para `examine`, un item revelado para `take`, o una llave/pieza del inventario para `use`.

Navegacion:
- En escenarios con `go`, manten un mapa mental de sala actual, salidas, camino recorrido, objetos vistos e inventario.
- La sala actual es siempre la ultima sala indicada por `look` o por una respuesta exitosa de `go` ("Llegas a ...").
- Antes de moverte, usa solo direcciones listadas para la sala actual por `look`, por la ultima observacion o por la memoria estructurada.
- Nunca uses salidas de salas anteriores para moverte desde la sala actual.
- Si una direccion falla desde una sala, recorda que esa direccion no existe desde esa sala y no la repitas.
- Si necesitas volver a un objeto visto antes, navega de regreso por el camino inverso registrado.
- Solo intentes `use(item, target)` si el target esta visible en la sala actual o en el inventario. Si no esta visible, volve primero a la sala donde lo viste.
- Nunca llames `go` con ids de objetos. `go` solo se usa con direcciones listadas en `Salidas`, como `norte`, `sur`, `este` u `oeste`.

Para memoria conversacional:
- Usa el historial como memoria de la conversacion.
- Si el usuario pide recordar un dato, confirmalo sin usar herramientas.
- Para preguntas sobre mensajes anteriores, responde usando el historial.

Para salida estructurada:
- Si cualquier tool devuelve que `puerta_principal` "Se abre", "esta abierta" o "ya esta abierta", el objetivo de abrir la puerta ya esta cumplido. Termina inmediatamente con respuesta final y no uses ninguna otra herramienta.
- Si `final_result` esta disponible, invoca esa herramienta con el schema pedido y no respondas con texto libre.

Cuando el objetivo este cumplido o tengas la respuesta final, responde directamente.
"""
),

        max_iterations: int = 45,
        max_history_messages: int = 80,
        use_structured_memory: bool = True,
    ) -> None:
        """Inicializa el agente.

        Parameters
        ----------
        llm_client : LLMClient
            Cliente LLM (real o mock) que el agente utilizará.
        system_prompt : str
            System prompt por defecto.
        max_iterations : int
            Tope de iteraciones del bucle del agente (M1).
        max_history_messages : int
            Número máximo de mensajes que se permiten en la lista
            `messages` enviada al LLM en una única llamada. En M1 este
            valor es ignorado; el agente sólo necesita aceptarlo en su
            constructor. En M2 deben respetarlo: la longitud de la
            lista de mensajes pasada a `self._llm.chat(...)` no puede
            superar este número en ninguna llamada, sin importar la
            estrategia de memoria que elijan.
        """
        if max_history_messages < 1:
            raise ValueError(
                f"max_history_messages debe ser >= 1 (recibido {max_history_messages}); "
                "con 0 no hay forma de mandarle ni un mensaje al LLM."
            )
        self._llm = llm_client
        self._system = system_prompt
        self._max_iterations = max_iterations
        self._max_history_messages = max_history_messages
        self._tools = {}
        self._schemas = {}
        # Historial persistente entre llamadas a run(): no incluye el
        # system prompt (eso se pasa aparte en cada chat(system=...)).
        self._history: list[dict[str, Any]] = []
        self._world_memory = WorldMemory() if use_structured_memory else None

    def register_tool(
        self,
        tool: Callable[..., str],
        schema: ToolSchema,
    ) -> None:
        """Registra una herramienta callable junto a su esquema.

        El esquema suele obtenerse con `ToolSchema.from_callable(fn)`. En
        `run`, pasá `tools=list(self._schemas.values())`; el cliente LLM
        aplica `to_llm_spec()` al llamar al proveedor.

        El callable se invoca con kwargs que coinciden con la firma.
        Debe devolver una cadena.
        """
        # self._tools: nombre -> callable, para ejecutar la tool cuando el LLM la pide.
        # self._schemas: nombre -> ToolSchema, para anunciarle al LLM qué tools existen
        # (se pasan en chat(tools=...)). Ambos indexados por schema.name, no por el
        # nombre de la variable Python.
        self._tools[schema.name] = tool
        self._schemas[schema.name] = schema

    @staticmethod
    def _split_into_units(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Agrupa `messages` en unidades atómicas, nunca partidas por la ventana:
        cada mensaje 'user' es su propia unidad; cada 'assistant' con tool_calls
        se agrupa junto con los 'tool' que le siguen inmediatamente (un
        tool_call sin su resultado, o viceversa, es un historial incoherente
        para el proveedor); cualquier otro mensaje (assistant de solo texto)
        es su propia unidad.
        """
        units: list[list[dict[str, Any]]] = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                unit = [msg]
                i += 1
                while i < len(messages) and messages[i].get("role") == "tool":
                    unit.append(messages[i])
                    i += 1
                units.append(unit)
            else:
                units.append([msg])
                i += 1
        return units

    def _apply_window(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Recorta `messages` a self._max_history_messages sin partir una unidad
        atómica, garantizando que el mensaje 'user' más reciente esté siempre
        presente (invariante de recencia) aunque el resto del contexto reciente
        deba descartarse para no superar el tope (nunca se supera el tope).
        """
        units = self._split_into_units(messages)
        if not units:
            return []

        last_user_idx = max(
            (i for i, u in enumerate(units) if u[0].get("role") == "user"),
            default=len(units) - 1,
        )
        selected = {last_user_idx}
        total = len(units[last_user_idx])

        for i in range(len(units) - 1, -1, -1):
            if i in selected:
                continue
            if total + len(units[i]) > self._max_history_messages:
                break
            selected.add(i)
            total += len(units[i])

        return [msg for i in sorted(selected) for msg in units[i]]

    def _call_with_retries(self, fn: Callable[..., Any], *args: Any, max_attempts: int = 3, **kwargs: Any) -> Any:
        """Reintenta `fn(*args, **kwargs)` ante fallos transitorios de red.

        "Transitorio" = una de `_TRANSIENT_EXCEPTIONS`, o un
        `botocore.ClientError` de throttling/servidor (ver
        `_is_transient_client_error`). Cualquier otra excepción se propaga
        en el primer intento, sin reintentar (no es un fallo que repetir
        la llamada vaya a arreglar).
        """
        last_error: BaseException | None = None
        for _ in range(max_attempts):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if not isinstance(e, self._TRANSIENT_EXCEPTIONS) and not self._is_transient_client_error(e):
                    raise
                last_error = e
        assert last_error is not None
        raise last_error

    def _system_for_run(self) -> str:
        if self._world_memory is None:
            return self._system
        return f"{self._system}\n\n{self._world_memory.to_prompt()}"

    def run(self, user_message: str) -> AgentResult:
        """Ejecuta el bucle del agente hasta una respuesta final o hasta max_iterations.

        Comportamiento esperado (consulta tests/conformance/test_m1.py
        para el contrato exacto del M1):
          - Llama a `self._llm.chat(..., tools=list(self._schemas.values()))`.
          - Si la respuesta contiene tool_calls, ejecuta cada uno y vuelca
            los resultados en la siguiente llamada al chat.
          - Si la respuesta solo contiene texto (sin `tool_calls`),
            devuélvelo en `AgentResult.answer`. En M1 no uses la tool
            sintética `final_result`; ese patrón es de M2 (ver README y
            ENUNCIADO_M2.md).
          - Limita el bucle a `self._max_iterations` y termina de forma
            limpia cuando se alcance.
          - Registra cada invocación de herramienta como un `AgentStep`
            dentro de `result.steps`.
            
        En el M2, además, llamadas sucesivas sobre la misma instancia
        deben continuar la conversación, y la longitud de la lista de
        mensajes enviada al LLM no debe superar `self._max_history_messages`.
        Acumula los tokens de entrada/salida reportados por los
        `LLMResponse` y exponlos en `AgentResult.input_tokens` /
        `AgentResult.output_tokens`.
        """
        self._history.append({"role": "user", "content": user_message})
        steps = []
        # Acumuladores de tokens de esta llamada a run(). Arrancan en None
        # (todavía no vimos ningún reporte); una vez que una respuesta
        # reporta un número, "(x or 0) + n" lo convierte a 0 antes de sumar,
        # y de ahí en más suma sobre un entero real. Si ninguna respuesta
        # reporta nunca, quedan en None hasta el final.
        input_tokens: int | None = None
        output_tokens: int | None = None

        # Tope de llamadas al LLM: evita loops infinitos si el modelo no
        # converge nunca a una respuesta de solo texto.
        for x in range(self._max_iterations):
            response = self._call_with_retries(
                self._llm.chat,
                messages=self._apply_window(self._history),
                # tools nunca es None: el contrato exige que el LLM vea
                # los esquemas disponibles desde la primera llamada.
                tools=list(self._schemas.values()),
                system=self._system_for_run(),
            )
            if response.input_tokens is not None:
                input_tokens = (input_tokens or 0) + response.input_tokens
            if response.output_tokens is not None:
                output_tokens = (output_tokens or 0) + response.output_tokens

            # Condición de parada normal: texto sin tool_calls = respuesta final.
            if not response.tool_calls:
                # Se guarda también en el historial: si no, el próximo run()
                # vería lo que dijo el usuario pero no lo que el agente
                # mismo respondió, rompiendo la continuidad de la charla.
                # El historial guarda lo que el modelo dijo tal cual (puede
                # ser ""); AgentResult.answer usa un fallback si vino vacío,
                # para no devolver nunca un answer vacío al usuario.
                self._history.append({"role": "assistant", "content": response.content or ""})
                return AgentResult(
                    answer=response.content or "El modelo no devolvió una respuesta de texto.",
                    steps=steps,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )

            # El LLM "pidió" usar tools: guardamos ese pedido como mensaje
            # assistant antes de ejecutar nada. El dict de tool_calls sigue
            # la forma {"function": {"name", "arguments"}} que esperan los
            # providers (Ollama/Bedrock) al normalizar el historial saliente
            # — no es un detalle de un proveedor en particular, es el
            # formato genérico del framework.
            self._history.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": tc.arguments},
                    }
                    for tc in response.tool_calls
                ],
            })
            for tool_call in response.tool_calls:
                # Un único try/except cubre: nombre de tool inexistente
                # (KeyError), JSON inválido en arguments (JSONDecodeError)
                # y cualquier excepción que tire la tool misma. Así el
                # agente nunca rompe run(), ni siquiera ante una tool
                # alucinada por el LLM.
                try:
                    tool = self._tools[tool_call.name]
                    kwargs = json.loads(tool_call.arguments)
                    # Solo la ejecución de la tool se envuelve con reintentos:
                    # un fallo transitorio (p. ej. un error de red dentro de
                    # la tool) se reintenta ciego; un nombre de tool
                    # inexistente o un JSON de argumentos inválido no son
                    # transitorios y se dejan propagar tal cual al except.
                    memory_error = (
                        self._world_memory.validate_action(
                            tool_name=tool_call.name,
                            tool_input=tool_call.arguments,
                        )
                        if self._world_memory is not None
                        else None
                    )
                    output = (
                        memory_error
                        if memory_error is not None
                        else self._call_with_retries(tool, **kwargs)
                    )
                    error = None
                except Exception as e:
                    output = None
                    error = str(e)

                # Un AgentStep por cada tool_call, sin importar si tuvo
                # éxito o no — error queda en None solo en el caso exitoso.
                steps.append(AgentStep(
                tool_name=tool_call.name,
                tool_input=tool_call.arguments,
                tool_output=output,
                error=error,
                ))
                if self._world_memory is not None:
                    self._world_memory.update(
                        tool_name=tool_call.name,
                        tool_input=tool_call.arguments,
                        tool_output=output,
                        error=error,
                    )

                # Realimentación al LLM: el resultado (o el error, como
                # texto) se vuelca como mensaje "tool" antes de la próxima
                # llamada a chat, para que el modelo pueda usarlo.
                self._history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_call.name,
                    "content": output if error is None else f"Error: {error}",
                })

        # Se agotaron las iteraciones sin llegar a una respuesta de solo
        # texto: igual devolvemos un AgentResult válido con lo ejecutado
        # hasta el corte (steps), nunca una excepción. Con max_iterations=0
        # el loop nunca corrió ni una vez (test_agente_max_iterations_cero
        # exige answer=="" en ese caso puntual); si sí corrió pero no
        # convergió, devolvemos un mensaje en vez de un string vacío.
        answer = (
            ""
            if self._max_iterations == 0
            else "No se pudo completar la tarea dentro del límite de iteraciones configurado."
        )
        return AgentResult(
            answer=answer,
            steps=steps,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    
    def structured_call(
        self,
        prompt: str,
        schema: Any,
        max_repair_attempts: int = 2,
    ) -> Any:
        """Pide al LLM una respuesta validada contra `schema` (M2).

        Obligatorio: herramienta sintética `final_result` (ver
        `mia_agents.final_result_tool_schema` / `FINAL_RESULT_TOOL_NAME`).
        El agente ofrece esa tool al LLM, valida los `arguments` del
        `tool_call` y reintenta con contexto de reparación si el modelo
        responde con texto libre o con argumentos inválidos.

        Implementa esto en el M2:
          - Pasa `tools=[final_result_tool_schema(schema)]` en cada
            llamada a `chat` dentro de este método.
          - Termina solo cuando llega un `tool_call` a `final_result`
            cuyos argumentos validan con `schema.model_validate(...)`.
          - Reintenta hasta `max_repair_attempts` incluyendo el fallo en
            los mensajes (respuesta previa, mensaje `tool`, o user de
            reparación).
          - Si tras los reintentos sigue fallando, levanta una excepción
            limpia (no devuelvas valores parciales ni `None` sin avisar).

        El M1 deja esto como stub; los tests de M2 verifican el contrato.
        """
        # Intercambio aislado: no toca self._history. Ver Fase 7 del plan
        # para la justificación (final_result no pertenece a la charla
        # que continúa run()).
        #
        # Diseño: en vez de acumular todo el historial de intentos
        # fallidos, cada ronda REINICIA `messages` a solo dos mensajes: el
        # prompt original + una nota con el último error. El LLM no
        # necesita ver la cadena completa de intentos previos para
        # corregirse, solo qué pedí y qué salió mal la última vez. Esto
        # mantiene la lista siempre chica (no hace falta podarla) y hace
        # estructuralmente imposible perder el prompt original, sin
        # importar cuántas reparaciones ocurran.
        prompt_msg = {"role": "user", "content": prompt}
        messages: list[dict[str, Any]] = [prompt_msg]
        tools = [final_result_tool_schema(schema)]
        last_error_detail = "no se recibió ninguna respuesta del LLM"

        # 1 intento original + max_repair_attempts reparaciones.
        for _ in range(1 + max_repair_attempts):
            # self._apply_window solo importa como resguardo ante un
            # max_history_messages absurdamente chico (1); en el uso
            # normal `messages` ya tiene a lo sumo 2 elementos.
            response = self._call_with_retries(
                self._llm.chat,
                messages=self._apply_window(messages),
                tools=tools,
                system=self._system,
            )

            if not response.tool_calls:
                # Caso "no": texto libre en vez de invocar final_result.
                last_error_detail = (
                    "Respondiste con texto libre. Tenés que invocar la "
                    f"herramienta '{FINAL_RESULT_TOOL_NAME}' con los argumentos "
                    "solicitados; no está permitido responder con texto."
                )
                messages = [prompt_msg, {"role": "user", "content": f"Tu intento anterior falló: {last_error_detail}"}]
                continue

            tool_call = response.tool_calls[0]

            if tool_call.name != FINAL_RESULT_TOOL_NAME:
                # Caso "no": llamó a una tool que no es final_result.
                last_error_detail = (
                    f"Invocaste '{tool_call.name}', pero la única herramienta "
                    f"válida para terminar es '{FINAL_RESULT_TOOL_NAME}'."
                )
                messages = [prompt_msg, {"role": "user", "content": f"Tu intento anterior falló: {last_error_detail}"}]
                continue

            try:
                arguments = json.loads(tool_call.arguments)
            except json.JSONDecodeError as e:
                # Caso "no": arguments no es JSON válido.
                last_error_detail = f"Los argumentos no son JSON válido: {e}"
                messages = [prompt_msg, {"role": "user", "content": f"Tu intento anterior falló: {last_error_detail}"}]
                continue

            try:
                return schema.model_validate(arguments)
            except ValidationError as e:
                # Caso "no": JSON válido, pero no cumple el schema.
                last_error_detail = f"Los argumentos no cumplen el schema esperado: {e}"
                messages = [prompt_msg, {"role": "user", "content": f"Tu intento anterior falló: {last_error_detail}"}]
                continue

        # Se agotaron los intentos sin llegar al caso "sí": nunca devolvemos
        # None ni una instancia parcial, cortamos con una excepción clara.
        raise StructuredOutputError(
            f"No se pudo obtener una salida estructurada válida para "
            f"{schema!r} tras {max_repair_attempts} reparaciones. "
            f"Último error: {last_error_detail}"
        )
