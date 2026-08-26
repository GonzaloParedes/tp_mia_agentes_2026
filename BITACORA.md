# M3 - Observaciones

---

## Baseline

Nuestro agente inicial se buildea con las tools de M1, calculator, file_reader, y text_search

Ahora para el M3 se agregan ***look, examine, take, use, go*** (si el escenario tiene varias salas)

**Capacidades:**

- loop ReAct básico: LLM decide tool call, python ejecuta la tool, el resultado vuelve al LLM, repite.
- registro dinámico de tools (register_tool)
- memoria conversacional en self._history
- ventana de memoria limitada con max_history_messages=50
- límite anti-loop con max_iterations=10
- manejo de tool desconocida o argumentos inválidos sin romper todo
- retries para errores transitorios de LLM/tools
- conteo de tokens si Bedrock/Ollama los reportan


Lo que NO tiene todavía:

- prompt especializado para sala de escape;
- memoria estructurada de mapa/inventario;
- planner explícito;
- evaluación automática eval/run.py;
- clasificación de errores;
- experimentos/ablaciones;
- optimización de max_iterations para escenarios largos.

---

## Easy

```JSON
(.venv) PS C:\dev\MIA_repos\tp_mia_agentes_2026> python -m mia_world.cli run --scenario easy            
# Escenario: study-with-key (easy)                         
# Un estudio con una llave dorada bajo la alfombra y una puerta cerrada.
                                                                      
{                                                                                                                  
  "scenario": "study-with-key",                                                                                    
  "difficulty": "easy",                                                                                            
  "goal": {                                                                                                        
    "type": "item_open",                                                                                           
    "item": "puerta_principal"                                                                                     
  },                                                                                                               
  "goal_achieved": true,                                                                                           
  "goal_reason": "puerta principal está abierta",                                             
  "agent_result": {
    "answer": "<thinking>He logrado abrir la puerta principal usando la llave dorada. Ahora puedo salir del estudio.</thinking> ",
    "steps": [
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Estudio.\nUn estudio pequeño forrado de libros. Una alfombra persa cubre el centro del suelo. A un lado hay un escritorio de roble. Al fondo, la puerta principal.\nVes:\n  - alfombra [id: alfombra]\n  - escritorio [id: escritorio]\n  - puerta principal [id: puerta_principal] (cerrada)",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"alfombra\"}",
        "tool_output": "alfombra: Una vieja alfombra persa. Algo abulta debajo.\nContiene:\n  - llave dorada [id: llave_oro]",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"escritorio\"}",
        "tool_output": "escritorio: Un escritorio de roble con dos cajones. Ambos están abiertos y vacíos.\nEstá vacío.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_oro\", \"target\": \"puerta_principal\"}",
        "tool_output": "Error: no llevas ningún 'llave_oro'.",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_oro\"}",
        "tool_output": "Tomas llave dorada.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_oro\", \"target\": \"puerta_principal\"}",
        "tool_output": "Usas llave dorada con puerta principal. Se abre.",
        "error": null
      }
    ],
    "error": null,
    "input_tokens": 12448,
    "output_tokens": 395
  }
}
```

- Cuando el agente ve que dentro de un objeto hay otro, la primer acción NO es agarrar ese objeto, sino que sigue observando que hay a su alrededor.
- Recién cuando ve que necesita la llave para abrir la puerta, vuelve a buscarla.

### Prueba pasada.

---

## Color-locks

```JSON
# Escenario: color-locks (medium)
# Un sótano con cuatro cofres pintados de colores distintos. Cada cofre tiene una cerradura del mismo color, y cada uno (excepto uno) guarda dentro la llave del color del siguiente cofre. La cadena empieza con una llave plateada a la vista y termina con la llave dorada que abre la puerta principal.

{
  "scenario": "color-locks",
  "difficulty": "medium",
  "goal": {
    "type": "item_open",
    "item": "puerta_principal"
  },
  "goal_achieved": false,
  "goal_reason": "puerta principal está cerrada",
  "agent_result": {
    "answer": "<thinking>Los cofres plateado, rojo y verde están cerrados con llave y no puedo ver su interior. Parece que no hay otra manera de encontrar una llave para la puerta principal. Necesitaré buscar otra solución para salir del sótano.</thinking>",
    "steps": [
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave plateada\"}",
        "tool_output": "Error: no existe ningún objeto con id 'llave plateada'.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre plateado\"}",
        "tool_output": "Error: no existe ningún objeto con id 'cofre plateado'.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre rojo\"}",
        "tool_output": "Error: no existe ningún objeto con id 'cofre rojo'.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre verde\"}",
        "tool_output": "Error: no existe ningún objeto con id 'cofre verde'.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre azul\"}",
        "tool_output": "Error: no existe ningún objeto con id 'cofre azul'.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Sótano.\nUn sótano de piedra con olor a humedad y una bombilla solitaria colgando del techo. Una repisa baja en la pared norte sostiene una llave plateada brillante. En el suelo descansan cuatro cofres pintados de colores distintos. Al fondo, una puerta de roble con cerradura dorada.\nVes:\n  - llave plateada [id: llave_plata]\n  - cofre plateado [id: cofre_plata] (cerrada)\n  - cofre rojo [id: cofre_rojo] (cerrada)\n  - cofre verde [id: cofre_verde] (cerrada)\n  - cofre azul [id: cofre_azul]\n  - puerta principal [id: puerta_principal] (cerrada)",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_plata\"}",
        "tool_output": "Tomas llave plateada.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_plata\"}",
        "tool_output": "cofre plateado: Un cofre pequeño con tachuelas plateadas y una cerradura del mismo color. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_rojo\"}",
        "tool_output": "cofre rojo: Un cofre mediano pintado de rojo, con una cerradura roja del mismo tono. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_verde\"}",
        "tool_output": "cofre verde: Un cofre grande pintado de verde, con una cerradura verde voluminosa. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_azul\"}",
        "tool_output": "cofre azul: Un cofre pintado de azul desconchado. Sorprendentemente, no tiene cerradura: las bisagras se abren al primer empujón.\nContiene:\n  - trapo viejo [id: trapo_viejo]",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_plata\", \"target\": \"puerta_principal\"}",
        "tool_output": "Intentas usar llave plateada con puerta principal, pero no encaja.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_plata\"}",
        "tool_output": "cofre plateado: Un cofre pequeño con tachuelas plateadas y una cerradura del mismo color. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_rojo\"}",
        "tool_output": "cofre rojo: Un cofre mediano pintado de rojo, con una cerradura roja del mismo tono. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_verde\"}",
        "tool_output": "cofre verde: Un cofre grande pintado de verde, con una cerradura verde voluminosa. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_azul\"}",
        "tool_output": "cofre azul: Un cofre pintado de azul desconchado. Sorprendentemente, no tiene cerradura: las bisagras se abren al primer empujón.\nContiene:\n  - trapo viejo [id: trapo_viejo]",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_plata\"}",
        "tool_output": "cofre plateado: Un cofre pequeño con tachuelas plateadas y una cerradura del mismo color. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_rojo\"}",
        "tool_output": "cofre rojo: Un cofre mediano pintado de rojo, con una cerradura roja del mismo tono. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_verde\"}",
        "tool_output": "cofre verde: Un cofre grande pintado de verde, con una cerradura verde voluminosa. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      }
    ],
    "error": null,
    "input_tokens": 20836,
    "output_tokens": 696
  }
}
```

- Vemos que no para de observar cofres iterativamente, cuando al mirar la habitacion el agente deberia relacionar que si, hay una llave plateada, y un cofre plateado, y encaja la llave en el. Deberia probar abrir.

Modifico el default prompt del agente, por uno estructurado para especializarlo en resolución de salas de escape:


```python
"""Sos un agente con herramientas. Respondés en español y resolvés tareas paso a paso usando las herramientas disponibles.

Reglas generales:
- Usá herramientas cuando sean necesarias para observar, calcular, leer archivos o actuar sobre un entorno.
- Copiá exactamente los ids, rutas y argumentos que devuelven las herramientas. No reemplaces ids por nombres visibles.
- Si una herramienta devuelve un error por id inexistente, usá `look` u otra observación disponible para obtener el id correcto.
- No repitas la misma llamada si ya devolvió la misma información o el mismo error.
- Si examinas un contenedor y ves que requiere una llave o pieza para abrir, si antes no le hiciste `take` a la llave/pieza, no intentes abrir el contenedor, primero tomá la llave/pieza y después usala sobre el contenedor.
- Ante un error de herramienta, corregí la causa antes de intentar otra vez.

Para mundos tipo sala de escape:
- Empezá con `look` si no conocés el estado actual.
- `look` muestra objetos con formato `[id: ...]`; usá siempre esos ids exactos.
- examiná todos los objetos que ves con `look` para entenderlos antes de intentar `take` o `use`.
- Si ves un objeto tomable útil, usá `take` con su id.
- Si un objeto parece contenedor o está cerrado, usá `examine` para entenderlo.
- Si un contenedor está cerrado y tenés una llave o pieza compatible, usá primero `use(item, target)`; no sigas examinando el mismo contenedor cerrado.
- Si una llave o pieza comparte alguna similaridad o patrón con un contenedor cerrado, probá `use` sobre ese contenedor antes de seguir buscando.
- Después de abrir un contenedor, usá `examine` sobre ese contenedor para revelar su contenido.
- Después de revelar un item útil, tomalo con `take`.
- En escenarios con `go`, recordá salidas, sala actual, inventario y objetos pendientes. Volvé a salas anteriores cuando encuentres nuevas llaves o piezas.

Para salida estructurada:
- Si `final_result` está disponible, invocá esa herramienta con el schema pedido y no respondas con texto libre.

Cuando el objetivo esté cumplido o tengas la respuesta final, respondé directamente.
  """
```

```JSON
# Escenario: color-locks (medium)
# Un sótano con cuatro cofres pintados de colores distintos. Cada cofre tiene una cerradura del mismo color, y cada uno (excepto uno) guarda dentro la llave del color del siguiente cofre. La cadena empieza con una llave plateada a la vista y termina con la llave dorada que abre la puerta principal.

{
  "scenario": "color-locks",
  "difficulty": "medium",
  "goal": {
    "type": "item_open",
    "item": "puerta_principal"
  },
  "goal_achieved": true,
  "goal_reason": "puerta principal está abierta",
  "agent_result": {
    "answer": "<thinking>La puerta principal se abrió con la llave dorada. Ahora puedo salir del sótano.</thinking>\n\n\n\n<final_result>Has salido del sótano.</final_result>",
    "steps": [
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Sótano.\nUn sótano de piedra con olor a humedad y una bombilla solitaria colgando del techo. Una repisa baja en la pared norte sostiene una llave plateada brillante. En el suelo descansan cuatro cofres pintados de colores distintos. Al fondo, una puerta de roble con cerradura dorada.\nVes:\n  - llave plateada [id: llave_plata]\n  - cofre plateado [id: cofre_plata] (cerrada)\n  - cofre rojo [id: cofre_rojo] (cerrada)\n  - cofre verde [id: cofre_verde] (cerrada)\n  - cofre azul [id: cofre_azul]\n  - puerta principal [id: puerta_principal] (cerrada)",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_plata\"}",
        "tool_output": "Tomas llave plateada.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_plata\"}",
        "tool_output": "cofre plateado: Un cofre pequeño con tachuelas plateadas y una cerradura del mismo color. Encaja con una llave del mismo color.\nEstá cerrado con llave. No puedes ver el interior hasta abrirlo.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_plata\", \"target\": \"cofre_plata\"}",
        "tool_output": "Usas llave plateada con cofre plateado. Se abre.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_plata\"}",
        "tool_output": "cofre plateado: Un cofre pequeño con tachuelas plateadas y una cerradura del mismo color. Encaja con una llave del mismo color.\nContiene:\n  - llave roja [id: llave_roja]",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_roja\"}",
        "tool_output": "Tomas llave roja.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_roja\", \"target\": \"cofre_rojo\"}",
        "tool_output": "Usas llave roja con cofre rojo. Se abre.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_rojo\"}",
        "tool_output": "cofre rojo: Un cofre mediano pintado de rojo, con una cerradura roja del mismo tono. Encaja con una llave del mismo color.\nContiene:\n  - llave verde [id: llave_verde]",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_verde\"}",
        "tool_output": "Tomas llave verde.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_verde\", \"target\": \"cofre_verde\"}",
        "tool_output": "Usas llave verde con cofre verde. Se abre.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cofre_verde\"}",
        "tool_output": "cofre verde: Un cofre grande pintado de verde, con una cerradura verde voluminosa. Encaja con una llave del mismo color.\nContiene:\n  - llave dorada [id: llave_oro]",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_oro\"}",
        "tool_output": "Tomas llave dorada.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_oro\", \"target\": \"puerta_principal\"}",
        "tool_output": "Usas llave dorada con puerta principal. Se abre.",
        "error": null
      }
    ],
    "error": null,
    "input_tokens": 37271,
    "output_tokens": 859
  }
```

Paso la prueba.

Solo un inconveniente, el agente hizo:

```
examine cofre_plata
use llave_plata cofre_plata
examine cofre_plata
```

cuando lo óptimo esperado era:

```
take llave_plata
use llave_plata cofre_plata
examine cofre_plata
```

---

## Apartment Keys

```JSON
# Escenario: apartment-keys (medium)
# Un apartamento de tres ambientes conectados. La llave de la puerta principal está guardada en un cajón de la cocina, al otro extremo del recorrido. Hay que navegar entre salas, encontrar la llave y volver al recibidor para usarla.

{
  "scenario": "apartment-keys",
  "difficulty": "medium",
  "goal": {
    "type": "item_open",
    "item": "puerta_principal"
  },
  "goal_achieved": true,
  "goal_reason": "puerta principal está abierta",
  "agent_result": {
    "answer": "No se pudo completar la tarea dentro del límite de iteraciones configurado.",
    "steps": [
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Recibidor.\nUn recibidor estrecho con un perchero vacío y un espejo polvoriento. La puerta principal, de metal, está cerrada con una cerradura simple. Un pasillo se abre hacia el norte.\nVes:\n  - puerta principal [id: puerta_principal] (cerrada)\nSalidas: norte.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"norte\"}",
        "tool_output": "Caminas hacia norte. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Pasillo.\nUn pasillo en penumbra con cuadros torcidos. Conecta el recibidor al sur con la cocina al este.\nNo ves nada de interés.\nSalidas: este, sur.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"este\"}",
        "tool_output": "Caminas hacia este. Llegas a Cocina.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Cocina.\nUna cocina pequeña con azulejos blancos. Hay una mesada con un cajón cerrado y olor a café frío.\nVes:\n  - cajón de la cocina [id: cajon]\nSalidas: oeste.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cajon\"}",
        "tool_output": "cajón de la cocina: Un cajón de madera bajo la mesada. Se abre con un tirón y dentro hay cubiertos sueltos y algo más.\nContiene:\n  - llave dorada [id: llave_oro]",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_oro\"}",
        "tool_output": "Tomas llave dorada.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"sur\"}",
        "tool_output": "Error: no hay salida 'sur' desde aquí. Salidas disponibles: oeste.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"oeste\"}",
        "tool_output": "Caminas hacia oeste. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"sur\"}",
        "tool_output": "Caminas hacia sur. Llegas a Recibidor.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_oro\", \"target\": \"puerta_principal\"}",
        "tool_output": "Usas llave dorada con puerta principal. Se abre.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"fuera\"}",
        "tool_output": "Error: no hay salida 'fuera' desde aquí. Salidas disponibles: norte.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Recibidor.\nUn recibidor estrecho con un perchero vacío y un espejo polvoriento. La puerta principal, de metal, está cerrada con una cerradura simple. Un pasillo se abre hacia el norte.\nVes:\n  - puerta principal [id: puerta_principal] (abierta)\nSalidas: norte.\nLlevas: llave dorada [id: llave_oro].",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"norte\"}",
        "tool_output": "Caminas hacia norte. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Pasillo.\nUn pasillo en penumbra con cuadros torcidos. Conecta el recibidor al sur con la cocina al este.\nNo ves nada de interés.\nSalidas: este, sur.\nLlevas: llave dorada [id: llave_oro].",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"este\"}",
        "tool_output": "Caminas hacia este. Llegas a Cocina.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Cocina.\nUna cocina pequeña con azulejos blancos. Hay una mesada con un cajón cerrado y olor a café frío.\nVes:\n  - cajón de la cocina [id: cajon]\nSalidas: oeste.\nLlevas: llave dorada [id: llave_oro].",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cajon\"}",
        "tool_output": "cajón de la cocina: Un cajón de madera bajo la mesada. Se abre con un tirón y dentro hay cubiertos sueltos y algo más.\nEstá vacío.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Cocina.\nUna cocina pequeña con azulejos blancos. Hay una mesada con un cajón cerrado y olor a café frío.\nVes:\n  - cajón de la cocina [id: cajon]\nSalidas: oeste.\nLlevas: llave dorada [id: llave_oro].",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"oeste\"}",
        "tool_output": "Caminas hacia oeste. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"sur\"}",
        "tool_output": "Caminas hacia sur. Llegas a Recibidor.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"norte\"}",
        "tool_output": "Caminas hacia norte. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"este\"}",
        "tool_output": "Caminas hacia este. Llegas a Cocina.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"oeste\"}",
        "tool_output": "Caminas hacia oeste. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"sur\"}",
        "tool_output": "Caminas hacia sur. Llegas a Recibidor.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"norte\"}",
        "tool_output": "Caminas hacia norte. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"este\"}",
        "tool_output": "Caminas hacia este. Llegas a Cocina.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"oeste\"}",
        "tool_output": "Caminas hacia oeste. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"sur\"}",
        "tool_output": "Caminas hacia sur. Llegas a Recibidor.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"norte\"}",
        "tool_output": "Caminas hacia norte. Llegas a Pasillo.",
        "error": null
      }
    ],
    "error": null,
    "input_tokens": 100368,
    "output_tokens": 1417
  }
}
```

Observamos que, logra el objetivo, pero el agente no se da cuenta que cumplió y continua viajando entre habitaciones. 

Agrego en el prompt:

```python
- Recorda cual es el objetivo principal, y si la cumplís, respondé directamente con la respuesta final sin usar herramientas.
```

Resultado:

```JSON
# Escenario: apartment-keys (medium)
# Un apartamento de tres ambientes conectados. La llave de la puerta principal está guardada en un cajón de la cocina, al otro extremo del recorrido. Hay que navegar entre salas, encontrar la llave y volver al recibidor para usarla.

{
  "scenario": "apartment-keys",
  "difficulty": "medium",
  "goal": {
    "type": "item_open",
    "item": "puerta_principal"
  },
  "goal_achieved": true,
  "goal_reason": "puerta principal está abierta",
  "agent_result": {
    "answer": "<thinking>La puerta principal se abrió con éxito usando la llave dorada. Ahora puedo salir del apartamento.</thinking>\n\nLa puerta principal se abrió con éxito usando la llave dorada. Ahora puedes salir del apartamento.",
    "steps": [
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Recibidor.\nUn recibidor estrecho con un perchero vacío y un espejo polvoriento. La puerta principal, de metal, está cerrada con una cerradura simple. Un pasillo se abre hacia el norte.\nVes:\n  - puerta principal [id: puerta_principal] (cerrada)\nSalidas: norte.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"norte\"}",
        "tool_output": "Caminas hacia norte. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Pasillo.\nUn pasillo en penumbra con cuadros torcidos. Conecta el recibidor al sur con la cocina al este.\nNo ves nada de interés.\nSalidas: este, sur.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"este\"}",
        "tool_output": "Caminas hacia este. Llegas a Cocina.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Cocina.\nUna cocina pequeña con azulejos blancos. Hay una mesada con un cajón cerrado y olor a café frío.\nVes:\n  - cajón de la cocina [id: cajon]\nSalidas: oeste.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"cajon\"}",
        "tool_output": "cajón de la cocina: Un cajón de madera bajo la mesada. Se abre con un tirón y dentro hay cubiertos sueltos y algo más.\nContiene:\n  - llave dorada [id: llave_oro]",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_oro\"}",
        "tool_output": "Tomas llave dorada.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"sur\"}",
        "tool_output": "Error: no hay salida 'sur' desde aquí. Salidas disponibles: oeste.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"oeste\"}",
        "tool_output": "Caminas hacia oeste. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_oro\", \"target\": \"puerta_principal\"}",
        "tool_output": "Error: no ves ningún 'puerta_principal' aquí.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"oeste\"}",
        "tool_output": "Error: no hay salida 'oeste' desde aquí. Salidas disponibles: este, sur.",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"este\"}",
        "tool_output": "Caminas hacia este. Llegas a Cocina.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Cocina.\nUna cocina pequeña con azulejos blancos. Hay una mesada con un cajón cerrado y olor a café frío.\nVes:\n  - cajón de la cocina [id: cajon]\nSalidas: oeste.\nLlevas: llave dorada [id: llave_oro].",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"oeste\"}",
        "tool_output": "Caminas hacia oeste. Llegas a Pasillo.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Pasillo.\nUn pasillo en penumbra con cuadros torcidos. Conecta el recibidor al sur con la cocina al este.\nNo ves nada de interés.\nSalidas: este, sur.\nLlevas: llave dorada [id: llave_oro].",
        "error": null
      },
      {
        "tool_name": "go",
        "tool_input": "{\"direction\": \"sur\"}",
        "tool_output": "Caminas hacia sur. Llegas a Recibidor.",
        "error": null
      },
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Recibidor.\nUn recibidor estrecho con un perchero vacío y un espejo polvoriento. La puerta principal, de metal, está cerrada con una cerradura simple. Un pasillo se abre hacia el norte.\nVes:\n  - puerta principal [id: puerta_principal] (cerrada)\nSalidas: norte.\nLlevas: llave dorada [id: llave_oro].",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_oro\", \"target\": \"puerta_principal\"}",
        "tool_output": "Usas llave dorada con puerta principal. Se abre.",
        "error": null
      }
    ],
    "error": null,
    "input_tokens": 53927,
    "output_tokens": 930
  }
}
```

Observaciones:

La ruta óptima era:

```
look
go norte
go este
examine cajon
take llave_oro
go oeste
go sur
use llave_oro puerta_principal
```

Pero la ejecucion dio 18 steps, con errores:

go sur desde Cocina -> Error, solo hay oeste
use puerta_principal desde Pasillo -> Error, no la ve
go oeste desde Pasillo -> Error, salidas este/sur

***Claramente es un error de MEMORIA. La siguiente mejora debería apuntar a memoria de mapa.** *

Indicando en el prompt como recordar la navegación, mejoran los resultados. De 18 a 11 steps ahora.

```
"""Sos un agente con herramientas. Respondés en español y resolvés tareas paso a paso usando las herramientas disponibles.

Reglas generales:
- Usá herramientas cuando sean necesarias para observar, calcular, leer archivos o actuar sobre un entorno.
- Copiá exactamente los ids, rutas y argumentos que devuelven las herramientas. No reemplaces ids por nombres visibles.
- Si una herramienta devuelve un error por id inexistente, usá `look` u otra observación disponible para obtener el id correcto.
- No repitas la misma llamada si ya devolvió la misma información o el mismo error.
- Ante un error de herramienta, corregí la causa antes de intentar otra vez.

Para mundos tipo sala de escape:
- Empezá con `look` si no conocés el estado actual.
- `look` muestra objetos con formato `[id: ...]`; usá siempre esos ids exactos.
- Examiná objetos selectivamente para entender contenedores, cerraduras, pistas u objetos sospechosos; no examines todo si ya hay una acción útil evidente.
- Si ves un objeto tomable útil, usá `take` con su id.
- Si tenés una llave o pieza y hay un contenedor/cerradura compatible por color, nombre o descripción, probá `use(item, target)` antes de seguir explorando.
- Si un contenedor u objeto cerrado requiere una llave o pieza que todavía no tenés en el inventario, no intentes abrirlo: buscá, revelá y tomá primero el item requerido.
- No sigas examinando el mismo contenedor cerrado si ya sabés que requiere una llave/pieza; abrilo primero cuando tengas el item compatible.
- Después de abrir un contenedor, usá `examine` sobre ese contenedor para revelar su contenido.
- Después de revelar un item útil, tomalo con `take`.
- Recordá el objetivo principal. Si una tool confirma que el objetivo ya se cumplió, no uses más herramientas y respondé con la respuesta final.
- Si `use(item, "puerta_principal")` devuelve que la puerta se abre, terminá inmediatamente con respuesta final. No llames `look`, `go`, `examine`, `take` ni `use` después de eso.

Navegación:
- En escenarios con `go`, mantené un mapa mental de sala actual, salidas, camino recorrido, objetos vistos e inventario.
- Antes de moverte, usá solo direcciones listadas para la sala actual por `look` o por la última observación.
- Si una dirección falla desde una sala, recordá que esa dirección no existe desde esa sala y no la repitas.
- Si necesitás volver a un objeto visto antes, navegá de regreso por el camino inverso registrado.
- Solo intentes `use(item, target)` si el target está visible en la sala actual o en el inventario. Si no está visible, volvé primero a la sala donde lo viste.
- La sala actual es siempre la última sala indicada por `look` o por una respuesta exitosa de `go` ("Llegas a ..."). Antes de llamar `go`, verificá las salidas conocidas de esa sala actual; no uses salidas de salas anteriores.

Para memoria conversacional:
- Usá el historial como memoria de la conversación.
- Si el usuario pide recordar un dato, confirmalo sin usar herramientas.
- Para preguntas sobre mensajes anteriores, respondé usando el historial.

Para salida estructurada:
- Si `final_result` está disponible, invocá esa herramienta con el schema pedido y no respondas con texto libre.

Cuando el objetivo esté cumplido o tengas la respuesta final, respondé directamente."""
```

Hasta aca cumple, no de forma óptima pero cumple, vamos con la última sala.

---

## Library-search

Tiene como inconveniente que se genera un loop de look cuando el historial se carga con informacion de cada libro. 

Agregamos una política anti-loop en el prompt. 

```python
- Si examinás varios objetos similares y no encontrás nada útil, continuá con el siguiente id pendiente de la lista revelada; no vuelvas a `look` salvo que hayas agotado la lista o cambiado de sala/estado.
- No llames `look` repetidamente en la misma sala si la observación no cambió. Si no avanzaste, elegí un objeto pendiente para `examine`, un item revelado para `take`, o una llave/pieza del inventario para `use`.
```

Paso la prueba:

```JSON
# Escenario: library-search (hard)
# Una biblioteca con ocho libros en una estantería alta. Uno de ellos guarda la llave de la caja fuerte; la caja, a su vez, contiene la llave grabada que abre la puerta. Los demás libros son prosa larga e inútil.

{
  "scenario": "library-search",
  "difficulty": "hard",
  "goal": {
    "type": "item_open",
    "item": "puerta_principal"
  },
  "goal_achieved": true,
  "goal_reason": "puerta principal está abierta",
  "agent_result": {
    "answer": "<thinking>La puerta principal se abrió con la llave grabada. He logrado salir de la biblioteca del archivero.</thinking>\n\nLa respuesta final es: Has logrado salir de la biblioteca del archivero.",
    "steps": [
      {
        "tool_name": "look",
        "tool_input": "{}",
        "tool_output": "Estás en Biblioteca del archivero.\nUna sala rectangular con olor a papel viejo. Al norte, una estantería alta de roble cargada de libros antiguos. En el centro, un escritorio robusto con un cajón único, vacío al primer vistazo. En la pared oeste, empotrada en el muro, una caja fuerte de hierro con bisagras macizas y un disco de combinación que en realidad oculta una cerradura convencional. Enfrente, la puerta principal, de hierro negro, con la cerradura grabada de símbolos.\nVes:\n  - escritorio [id: escritorio]\n  - estantería alta [id: estanteria_alta]\n  - caja fuerte [id: caja_fuerte] (cerrada)\n  - puerta principal [id: puerta_principal] (cerrada)",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"estanteria_alta\"}",
        "tool_output": "estantería alta: Una estantería de roble de cuatro baldas. Solo la balda superior tiene libros — ocho volúmenes encuadernados con materiales distintos pero de tamaño parecido. Las baldas inferiores están vacías.\nContiene:\n  - Elementos de geometría aplicada [id: libro_geometria]\n  - Notas sobre la transmutación de los metales [id: libro_alquimia]\n  - Diálogos sobre la naturaleza del juicio [id: libro_filosofia]\n  - Anales del reino, década quinta [id: libro_historia]\n  - Recopilación de sentencias del tribunal supremo [id: libro_jurisprudencia]\n  - Recetario del cocinero mayor [id: libro_recetario]\n  - Genealogía de la casa de Andrade [id: libro_genealogia]\n  - Colección de sermones dominicales [id: libro_sermones]",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"escritorio\"}",
        "tool_output": "escritorio: Un escritorio de roble con un único cajón estrecho. Lo abres y lo encuentras vacío salvo por restos de polvo y una pluma rota.\nEstá vacío.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_geometria\"}",
        "tool_output": "Elementos de geometría aplicada: Encuadernación rígida de cartón forrado en tela negra, lomo reforzado. Proposición XVII (página 84): 'En todo triángulo, si se prolongan dos de sus lados hasta cortarse en un punto exterior, los ángulos así formados son iguales a los ángulos opuestos por el vértice del triángulo original.' La demostración ocupa página y media y se apoya en las proposiciones IV, IX y XII. El autor — Tomás del Riego, ingeniero militar — añade en nota al pie que esta proposición le ahorró tres días de cálculo en el trazado del fuerte de San Marcos, en el año 1721, y recomienda al lector aplicarla con prudencia cuando la regla no alcance. El resto del capítulo desarrolla seis problemas resueltos sobre triángulos semejantes, cuadrados inscritos en círculos y trazado de polígonos regulares de cinco, seis y ocho lados. Las figuras están grabadas en cobre y aparecen al pie de cada problema, con líneas de construcción discontinuas y letras latinas para los vértices.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_alquimia\"}",
        "tool_output": "Notas sobre la transmutación de los metales: Manuscrito en cuarto, encuadernación de cuero rojo desgastado, sin nombre de autor. Folio 23 verso: 'Operación segunda: tomadas las virutas de plomo del peso de una onza y tres adarmes, póngase en crisol de arcilla refractaria, cúbrase con sal de tártaro y cal viva en partes iguales, y caliéntese al rojo cereza durante doce horas seguidas sin dejar enfriar el fuelle. Apartado del fuego, déjese reposar el crisol hasta la mañana siguiente. Al romperlo se hallará una masa vidriosa en cuya superficie aparecerán glóbulos del metal del sol; recójanse con espátula de cuerno, no de metal vulgar. Sucede a veces, no diré con qué frecuencia, que la operación produzca solo una escoria gris y maloliente; en tal caso conviene revisar la pureza de la cal y la quietud del firmamento.' El folio siguiente lleva una receta similar para la cal de mercurio. Hay marcas de quemaduras en los márgenes y manchas oscuras que el lector cuidadoso reconocerá como hierro oxidado.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_filosofia\"}",
        "tool_output": "Diálogos sobre la naturaleza del juicio: Volumen de pequeño tamaño, encuadernado en piel verde con cantos dorados. Diálogo tercero, entre Macario y Filón: '— Dime, Filón: cuando juzgas a tu vecino, ¿le pesas con la misma balanza con que te pesas a ti mismo? — A veces, Macario; pero he advertido que la balanza pierde fiel cuando se mira de cerca. — Es decir, que cuanto más te conoces, menos riguroso eres contigo. — Más bien lo contrario: cuanto más me conozco, más comprendo por qué fallo, y eso me hace indulgente conmigo y a veces injusto con los demás. — De suerte que la indulgencia y la injusticia nacen de la misma raíz. — Eso parece. — Concluyamos entonces que el juicio sano no nace de conocerse, sino de olvidarse: solo el juez que ha dejado fuera de la sala su propio caso puede pesar limpio.' El diálogo prosigue durante diez páginas más, sin que ninguno de los dos consienta del todo en la conclusión del otro. El autor — un canónigo de Salamanca — anota al margen: 'tampoco yo estoy seguro'.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_historia\"}",
        "tool_output": "Anales del reino, década quinta: Tomo en folio, encuadernación de pergamino crudo, con cintas de cierre. Año 1437, entrada de mayo: 'Llegó al puerto de Santander, en la víspera de san Pedro, una flota de tres naves procedentes de Flandes con cargamento de paño teñido, ámbar y libros impresos. La corona compró el ámbar por mil quinientos maravedís, y el paño quedó para el infante don Sancho. Los libros, traducidos por un fraile de Burgos, se enviaron a la biblioteca real. Las naves regresaron con plata mexicana y aceite andaluz.' Junio: 'Hubo plaga de langosta en los campos de Tierra de Campos, perdiéndose dos tercios de la cosecha. La corona dispensó del diezmo a las parroquias afectadas.' Julio: 'El conde de Treviño murió de fiebres, sin heredero legítimo, y sus posesiones revirtieron a la corona tras un pleito que duró seis meses.' Las entradas continúan así, mes por mes, hasta el año 1442. Los márgenes están salpicados de números: probables totales presupuestarios anotados por algún funcionario.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_jurisprudencia\"}",
        "tool_output": "Recopilación de sentencias del tribunal supremo: Tomo grueso encuadernado en piel parda, con el escudo real estampado en seco en la cubierta. Sentencia 412 del año 1798: 'En la causa seguida contra Juan Espinosa, vecino de Trujillo, por presunta apropiación indebida de aguas de regadío comunal, vista la prueba documental y testimonial aportada por ambas partes, este tribunal falla: el demandado deberá restituir a la comunidad de regantes la cantidad de tres cargas de cebada equivalentes al daño estimado, abonará costas, y se le impone censura pública en plaza por hábito reiterado de prácticas similares. No procede pena de cárcel por carecer el reo de antecedentes formales. Notifíquese a la autoridad municipal correspondiente.' Las sentencias siguientes versan sobre lindes de fincas, herencias mal repartidas y cobros de censos vencidos. El estilo es severo y conciso; las decisiones tienden a buscar la restitución antes que el castigo. Al final del tomo, un índice ordena los casos por materia: aguas, lindes, herencias, mercados, contratos.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_recetario\"}",
        "tool_output": "Recetario del cocinero mayor: Manuscrito en cuarto, tapas blandas de pergamino, manchado de aceite. Receta del capón en pepitoria, página 47: 'Tómese un capón joven, bien limpio y troceado, y póngase a dorar en cazuela de barro con manteca de cerdo y un poco de tocino. Cuando esté tomado por todos lados, añádase una cabeza de ajos picada, un puñado de almendras tostadas y machacadas, una cucharada de harina y un vaso del mejor vino blanco que se tenga. Déjese reducir un cuarto de hora a fuego mediano; añádanse después dos huevos cocidos, picado fino el blanco y reservada la yema. Cúbrase con caldo de gallina hasta que el capón quede sumergido, y cuézase a fuego lento durante hora y media. Al final, deslíase la yema de huevo en un poco de la salsa y añádase a la cazuela fuera del fuego, removiendo bien para que ligue. Espolvoréese perejil picado y sírvase muy caliente.' Las páginas siguientes detallan recetas de pichones, conejo, ternera estofada y un curioso pastel de hojaldre con manzana.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_genealogia\"}",
        "tool_output": "Genealogía de la casa de Andrade: Tomo grande encuadernado en piel azul, con grabados heráldicos en el lomo. Capítulo I — Origen y primera generación: 'Pero Domínguez de Andrade, llamado el Calvo por su temprana pérdida de cabello, fundó la casa en el año 1284 al recibir de don Sancho IV las tierras de Andrade en Tierra de Lemos, en pago por sus servicios en la frontera de Granada. Casó en primeras nupcias con doña Mencía Rodríguez, de la cual tuvo tres hijos: Fernán, Diego y Teresa. Enviudó en 1297 y casó de nuevo con doña Aldonza Pérez de Sarria, sin sucesión. Murió en 1312 de heridas mal cicatrizadas tras una caída de caballo.' El árbol genealógico ocupa una página plegada y baja hasta finales del siglo XVIII, con doce ramas principales y numerosas colaterales. Los nombres se repiten: Fernán, Sancho, Pero, Teresa, Mencía. Las anotaciones marginales indican fechas de nacimiento, casamientos, defunciones y, en algunos casos, una breve nota sobre el oficio o las circunstancias del fin.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"libro_sermones\"}",
        "tool_output": "Colección de sermones dominicales: Tomo encuadernado en piel negra con cantos rojos, muy usado. Sermón XXI, para el cuarto domingo de cuaresma: 'Mis hermanos, no es la enmienda lo que se nos pide, sino el principio de la enmienda; no la perfección, sino el ánimo de empezar. Cristo no espera al santo en el umbral de la iglesia: espera al pecador que se acerca. Si esto entendemos, lo demás vendrá; si esto no lo entendemos, ni con cuarenta días de ayuno ni con cuarenta noches en vela conseguiremos avanzar un palmo. La vida cristiana no es un palacio que uno construye desde fuera, piedra a piedra hasta dejarlo perfecto; es una casa heredada, que conviene barrer todos los días y reparar cuando algo se rompe.' El predicador — Fray Diego Méndez, dominico — repite la misma estructura en los sermones siguientes: una imagen sencilla, una insistencia, una invitación. El tomo está marcado en docenas de páginas con cintas de seda descoloridas; los márgenes llevan anotaciones de un párroco posterior.\nContiene:\n  - llave de la caja [id: llave_caja]",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_caja\"}",
        "tool_output": "Tomas llave de la caja.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_caja\", \"target\": \"caja_fuerte\"}",
        "tool_output": "Usas llave de la caja con caja fuerte. Se abre.",
        "error": null
      },
      {
        "tool_name": "examine",
        "tool_input": "{\"target\": \"caja_fuerte\"}",
        "tool_output": "caja fuerte: Caja fuerte de hierro empotrada en el muro. El disco de combinación visible es decorativo: la cerradura real está bajo una placa metálica que solo se abre con una llave específica.\nContiene:\n  - llave grabada [id: llave_grabada]",
        "error": null
      },
      {
        "tool_name": "take",
        "tool_input": "{\"item\": \"llave_grabada\"}",
        "tool_output": "Tomas llave grabada.",
        "error": null
      },
      {
        "tool_name": "use",
        "tool_input": "{\"item\": \"llave_grabada\", \"target\": \"puerta_principal\"}",
        "tool_output": "Usas llave grabada con puerta principal. Se abre.",
        "error": null
      }
    ],
    "error": null,
    "input_tokens": 74464,
    "output_tokens": 976
  }
}
```

---

## Office-sequence

El agente gastó 30 steps y se quedó sin iteraciones justo después de abrir la puerta.
Qué está pasando:

- Bien: respetó el orden crítico, tomó documento_confidencial antes de abrir.
- Mal: olvidó tomar llave_maestra cuando la vio junto al documento.
- Mal: intentó usar llave_maestra sin tenerla.
- Mal: volvió al archivo, la tomó, y repitió algunos movimientos erróneos.
- Mal: no cortó con respuesta final tras puerta_principal se abre, probablemente porque justo alcanzó el límite.

Mejoras:

```
- Si una observación revela varios items útiles en un contenedor abierto, tomá todos los items necesarios antes de irte de la sala. En particular, si aparecen un documento objetivo y una llave/pieza útil, tomá ambos antes de navegar.
- Antes de usar una llave/pieza, verificá que esté en el inventario según las observaciones previas. Si fue revelada pero no tomada, volvé al lugar donde la viste y usá `take` antes de intentar `use`.
```

Ahora el agente entra en loop con look luego de haber cumplido el objetivo. No identifica que salio de la sala de escape. Agrego en el prompt:

```
- Si cualquier tool devuelve que `puerta_principal` "Se abre", "está abierta" o "ya está abierta", el objetivo de abrir la puerta ya está cumplido. Terminá inmediatamente con respuesta final y no uses ninguna otra herramienta.
```
---

## Eval automatizado

Se implemento una primera version de `eval/run.py` para dejar la evaluacion de M3 reproducible.

- Lee el prompt especializado desde `M3-PROMPT`.
- Construye el agente con `build_agent(config)`, pasando `system_prompt`, `max_iterations` y `max_history_messages`.
- Registra las herramientas del mundo: `look`, `examine`, `take`, `use` y `go` cuando el escenario lo habilita.
- Permite correr un escenario puntual con `--scenario` o todos los escenarios si se omite ese argumento.
- Evalua con `check_goal`, no con el texto final del agente.
- Guarda `eval/results/latest/results.jsonl` y `eval/results/latest/summary.json`.
- Clasifica errores con reglas en Python, sin LLM: `navigation_error`, `repeated_action`, `repeated_look`, `post_goal_overrun`, `max_iterations`, `tool_error`, etc.

Comandos:

```powershell
.\.venv\Scripts\python.exe eval\run.py --scenario easy
.\.venv\Scripts\python.exe eval\run.py
```

---

## Comparacion de 3 experimentos de prompt

Se reviso la corrida `eval/results/experiments/20260821-110521`, con 8 escenarios y `max_iterations=30`, `max_history_messages=80`.

Resultados:

- `00-prompt_max_iterations`: sin prompt especializado. Paso 6/8 escenarios, `success_rate=0.75`, promedio de 18.12 tool calls y 469258 tokens totales.
- `01-prompt_max_iterations`: con `prompts/01_PROMPT`. Paso 6/8 escenarios, `success_rate=0.75`, promedio de 20.5 tool calls y 660913 tokens totales.
- `02-prompt_max_iterations`: con `prompts/02_PROMPT`. Paso 7/8 escenarios, `success_rate=0.875`, promedio de 21.75 tool calls y 866198 tokens totales.

Conclusion parcial:

- `02_PROMPT` es el mejor en accuracy: resuelve todos los escenarios easy, medium y hard, y 2/3 extreme.
- El costo sube bastante: `02_PROMPT` usa mas pasos y muchos mas tokens que la variante sin prompt.
- `01_PROMPT` no mejora la tasa de exito respecto de no usar prompt especializado, pero consume mas tokens.
- El unico fallo de `02_PROMPT` fue `vault-combination`. El agente vio `nucleo_rojo`, `llave_deposito` y `destornillador` en `banco_herramientas`, pero tomo solo `nucleo_rojo`; despues intento usar `llave_deposito` sin tenerla y entro en loop.
- Tambien quedan casos donde el mundo ya cumple el objetivo, pero el agente sigue actuando hasta el limite. Esto aparece como `post_goal_overrun` o `max_iterations` aunque `check_goal` marque el escenario como resuelto.

Proximo paso:

Probar una mejora de arquitectura con memoria estructurada, no solo prompt engineering. La memoria deberia registrar al menos:

- sala actual;
- salidas conocidas por sala;
- objetos vistos por sala;
- inventario observado;
- objetos revelados pero no tomados;
- acciones fallidas o repetidas.

La hipotesis es que esto deberia reducir errores de inventario, navegacion y repeticion, especialmente en `vault-combination`, `office-sequence` y escenarios con backtracking.

---

## Memoria estructurada pasiva

Se probo `04-structured-memory` comparando `prompts/03_PROMPT` sin memoria contra el mismo prompt con memoria estructurada pasiva.

Resultado:

- Sin memoria: 7/8 escenarios, `success_rate=0.875`.
- Con memoria pasiva: 6/8 escenarios, `success_rate=0.75`.

La memoria pasiva empeoro el resultado. El caso nuevo que fallo fue `office-sequence`: el agente llego al `Archivo`, vio la `caja_fuerte`, pero empezo a repetir navegacion invalida (`go este`) y vueltas entre `Archivo` y `Corredor`, sin ir al `Deposito` a buscar `llave_caja`.

Conclusion:

- Agregar memoria como texto extra en el system prompt no alcanza.
- La memoria agrego tokens y ruido, pero no impidio acciones contradictorias.
- El agente podia ignorar hechos como "desde Archivo solo existe salida sur" o "esta accion ya fallo".

Proximo paso:

Convertir la memoria en guardrails activos antes de ejecutar herramientas. Primero se probaran dos controles simples:

- bloquear `go` con direcciones que no existen desde la sala actual conocida;
- bloquear `use` si el item no esta en el inventario observado o fue revelado pero no tomado.

Implementacion:

Se agrego una primera version de memoria activa. Antes de ejecutar herramientas, el agente valida contradicciones fuertes contra la memoria:

- `go`: si la direccion no existe desde la sala actual conocida, no ejecuta la tool real y devuelve un error de memoria al LLM.
- `use`: si el item fue revelado pero no tomado, o no esta en el inventario observado, no ejecuta la tool real.
- `take` / `examine` / `use`: si el objeto fue visto en otra sala y la sala actual es distinta, se bloquea la accion y se pide navegar primero.

Esto convierte la memoria de contexto pasivo en una capa minima de control previo a herramientas.

---

## Resultado memoria activa y variabilidad

Se corrio `04-structured-memory` en `eval/results/experiments/structured-memory-active`.

Resultado dentro de la misma corrida:

- `00_prompt03_no_memory`: 5/8 escenarios, `success_rate=0.625`, 22.62 tool calls promedio, 849901 tokens.
- `01_prompt03_structured_memory`: 6/8 escenarios, `success_rate=0.75`, 19.88 tool calls promedio, 809373 tokens.

La memoria activa mejoro dentro de esta corrida: recupero `color-locks` y redujo `office-sequence` de 31 a 20 tool calls. Sin embargo, estos numeros no son directamente comparables contra el resultado anterior de `prompts/03_PROMPT` sin memoria, que habia dado 7/8, porque:

- el LLM no es deterministico (`temperature=0.2` por default);
- `prompts/03_PROMPT` tuvo cambios entre corridas;
- una sola corrida por variante es demasiado fragil para concluir.

Proximo ajuste de evaluacion:

Agregar soporte de multiples repeticiones por experimento (`--runs N`) y reportar promedios. La comparacion importante pasa a ser promedio de success rate, tool calls, tokens y errores acumulados por variante.

---

## Experimento focalizado: vault-combination y memoria estructurada

Se trabajo sobre `vault-combination` como escenario laboratorio porque era el fallo mas persistente en extreme.

Cambios probados:

- guardrail preventivo para no permitir `go` si en la sala actual hay objetos revelados pero no tomados;
- mensaje mas accionable cuando `go` usa una direccion invalida y la memoria conoce una unica salida valida;
- tracking generico de requisitos cuando una tool informa que a un objetivo le faltan piezas/items;
- `prompts/04_PROMPT`, derivado de `03_PROMPT`, con instrucciones explicitas para leer y priorizar la memoria estructurada.

Se descarto una idea que metia ruido: sugerir genericamente "probar items del inventario" contra targets conocidos. Aunque era general, hacia que el agente explorara combinaciones demasiado amplias y empeoraba el resultado.

Resultado de `06-prompt03-vs-04-memory` sobre `vault-combination` con 3 runs:

- `03_PROMPT` + memoria estructurada: 2/3, `success_rate=0.667`.
- `04_PROMPT` + memoria estructurada: 3/3, `success_rate=1.0`.

Conclusion:

El resultado sugiere que no alcanza con agregar memoria estructurada al system prompt: el prompt tambien debe explicar como usarla. `04_PROMPT` mejora porque le indica al agente revisar sala actual, inventario, objetos revelados no tomados, salidas conocidas, acciones fallidas y siguiente objetivo sugerido antes de cada tool call.

Proximo paso:

Correr `06-prompt03-vs-04-memory.json` en todos los escenarios para verificar que `04_PROMPT` no este sobreajustado a `vault-combination`.

---

## Dimension cualitativa automatizada

La consigna pide al menos una dimension cualitativa evaluada por rubrica o LLM-as-judge. Se implemento una rubrica automatica y reproducible en `eval/qualitative.py`.

Comando:

```powershell
.\.venv\Scripts\python.exe .\eval\qualitative.py --results-dir eval\results\latest
```

El script lee `results.jsonl` y genera:

- `qualitative_review.json`;
- `qualitative_review.md`.

Rubrica 0-3:

- 0: no progresa o no hay trayectoria evaluable;
- 1: progresa poco, se atasca o repite errores;
- 2: progresa parcialmente o resuelve con ruido importante;
- 3: resuelve con trayectoria coherente y sin repeticiones graves.

La clasificacion usa senales observables de la traza: exito del goal, errores de runner, cantidad de steps, progreso observable (`take`, aperturas, navegacion), errores de tools, acciones repetidas y limite de iteraciones.

Nota: si la corrida contiene `ExpiredTokenException` u otro `runner_error`, esos casos puntuan 0 porque no hay trayectoria del agente para evaluar. Para el informe final hay que correr esta rubrica sobre una evaluacion valida.
