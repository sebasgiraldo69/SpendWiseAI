# Reflexión — Sebastián

## ¿Qué cambió Codex?

Codex nos ayudó a separar responsabilidades que antes estaban mezcladas dentro del prompt. Ahora Gemini se encarga de interpretar el texto y extraer los movimientos, mientras que el código hace las sumas, calcula el saldo y obtiene el porcentaje gastado. También se agregó `validate_financial_output(output)`, que comprueba que estén todos los campos y que los totales sean consistentes.

Además, dejamos cinco casos de evaluación versionados y una forma de ejecutarlos desde el notebook. Esto nos permitió comparar el baseline, que obtuvo 4/5, con la versión mejorada, que obtuvo 5/5 en la ejecución guardada.

## ¿Qué riesgo técnico encontró?

El riesgo más importante era confiar en los números generados directamente por el modelo. Aunque Gemini devolviera un JSON válido, todavía podía sumar mal, duplicar un gasto ambiguo o inventar información debido a una instrucción maliciosa incluida en el texto del usuario.

El caso más claro fue el de los dos arriendos diferentes para el mismo mes. El baseline sumó ambos sin pedir confirmación. En información financiera, una respuesta con formato correcto pero con números equivocados sigue siendo un resultado peligroso.

## ¿Qué eval falla o falta?

En el baseline falló el caso del gasto duplicado ambiguo, por lo que el resultado inicial fue 4/5. Después de separar la extracción y los cálculos, los cinco casos pasaron y el resultado fue 5/5.

Sin embargo, todavía faltan pruebas para situaciones reales como valores negativos o devoluciones, ingreso igual a cero, diferentes monedas, formatos de números poco comunes, respuestas incompletas de Gemini y fallos de conexión o cuota de la API. También sería importante repetir varias veces los casos que dependen de IA, porque una sola ejecución no demuestra que el comportamiento sea estable.

Después de recibir la retroalimentación, agregamos casos para ingreso cero, valores escritos como “50 mil” o “1.2 millones”, monedas mezcladas, gastos sin monto, devoluciones y categorías ambiguas. La suite ampliada obtuvo 8/11. Fallaron el gasto sin valor, la devolución y la categoría ambigua: los números quedaron consistentes, pero el sistema no comunicó claramente la incertidumbre ni solicitó confirmación. Esto hace visible que los cálculos pueden estar perfectamente programados y aun así producir un resumen falso o incompleto si Gemini interpreta mal los movimientos originales.

## ¿Qué haríamos primero si esto fuera un producto real?

Primero convertiríamos estas evaluaciones en pruebas automáticas que se ejecuten con cada cambio. También guardaríamos los movimientos extraídos antes de calcular el resumen y le mostraríamos al usuario una pantalla de confirmación, especialmente cuando exista una ambigüedad.

Después probaríamos el flujo con usuarios reales y gastos anonimizados. Mediríamos errores de extracción, movimientos omitidos, duplicados y correcciones realizadas por las personas. Antes de pensar en recomendaciones más avanzadas, necesitamos demostrar que el sistema interpreta los gastos de manera confiable.

## ¿Qué parte del repo no aguantaría una revisión de un ingeniero senior?

La parte más débil sigue siendo que gran parte del producto vive dentro de un notebook. El notebook sirve para demostrar la idea, pero mezcla configuración, llamadas a Gemini, ejemplos, resultados guardados y lógica de ejecución. Esto hace más difícil probar, mantener y reutilizar el código.

Un ingeniero senior probablemente pediría mover toda la lógica a módulos con pruebas unitarias, definir un esquema estricto para la extracción, agregar manejo explícito de errores y configurar integración continua. También señalaría que obtener 5/5 con solo cinco casos es una buena señal inicial, pero todavía no es evidencia suficiente para afirmar que el sistema está listo para manejar información financiera real.
