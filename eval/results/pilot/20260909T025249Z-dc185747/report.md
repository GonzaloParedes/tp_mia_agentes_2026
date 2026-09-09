# Evaluacion: pilot

Estado: completed. Casos guardados: 12/12.

El exito se verifica sobre el estado del mundo. Los errores de ejecucion cuentan como fallos en estas metricas.
Los promedios incluyen exitos y fallos; una corrida incompleta no representa el plan completo.

La parada por objetivo, cuando esta activa, usa una comprobacion del entorno despues de cada herramienta.

| Variante | Parada por objetivo | Revision observacional | Exitos / casos | Exito | Tools promedio | Segundos promedio | Tokens |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| without_review | no | no | 6/6 | 100.0% | 26.17 | 25.246 | 737638 |
| with_review | no | si | 6/6 | 100.0% | 27.5 | 26.923 | 846743 |

Los tokens ausentes se contabilizan como cero en los agregados actuales.
Consultar summary.json para el desglose por escenario, repeticion y categorias; results.jsonl contiene las trazas.
