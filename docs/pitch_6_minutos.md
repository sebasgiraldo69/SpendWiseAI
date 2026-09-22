# Pitch de SpendWise AI · 6 minutos

Presentación navegable: iniciar `python app.py` y abrir http://127.0.0.1:8000/pitch. Flechas para avanzar, temporizador y exportación a PDF desde imprimir. Reparto sugerido: Sebastián abre/cierra y explica producto; Miguel muestra demo y arquitectura. Ambos deben poder responder todo.

Los bloques suman 360 segundos. El guion deja tiempo de interacción dentro de la demo; ensayar con cronómetro. No agregar funcionalidades ni resultados que no se hayan medido.

## 0:00–0:40 · Problema · Sebastián

“Somos Sebastián y Miguel y este es SpendWise AI. Nuestro usuario es un estudiante o joven profesional que anota gastos, pero al revisar el mes tiene que juntar textos, reconocer montos y organizar categorías antes de entender su presupuesto. La alternativa es hacerlo a mano en una hoja de cálculo. Nuestra hipótesis es que podemos reducir ese esfuerzo conservando el control de la persona. Todavía no tenemos pruebas con usuarios para afirmar que esa reducción ya ocurrió.”

## 0:40–1:10 · Producto y formato · Sebastián

“Elegimos una web app porque permite probar el flujo desde un navegador, sin instalar una aplicación móvil. Tiene tres pasos: contar los gastos, revisar lo interpretado y consultar el presupuesto. La IA aporta al interpretar lenguaje informal; las sumas no necesitan IA. También podemos cambiar la interfaz conservando el núcleo de cálculo y validación.”

## 1:10–3:10 · Demo · Miguel

Antes de empezar, decir la frase correspondiente:

- Si es Gemini: “Esta interpretación usa Gemini en tiempo real; después vamos a revisarla”.
- Si es ensayo: “Este es el modo de ensayo, con una extracción preparada manualmente. Sirve para demostrar el flujo; no lo presentamos como una llamada real de IA”.

**1:10–1:30:** abrir aplicación, ejemplo “Un mes completo”, interpretar.

“Entramos un ingreso de 2.800.000 pesos y los gastos del mismo periodo. El sistema separa cada movimiento y muestra la frase de la que salió.”

**1:30–1:55:** mostrar tabla, revisar, seleccionar escenario de restaurantes, marcar confirmación y calcular.

“Podemos corregir un monto o una categoría antes de confirmar. Aquí elegimos simular una reducción del diez por ciento en restaurantes. Es nuestra elección, y el ahorro de 30.000 pesos se calcula sobre ese gasto.”

**1:55–2:15:** mostrar gasto 2.626.800, saldo 173.200 y 93,81%; abrir evidencia si cabe.

“Python calcula los totales y valida que correspondan a los movimientos confirmados. El resultado conserva el modo usado y las correcciones.”

**2:15–2:50:** nuevo presupuesto, ejemplo “Un gasto sin monto”, interpretar. Mostrar mercado pendiente. Escribir 100000, marcar incluir y confirmar.

“Este caso dice que compramos mercado, pero no recordamos cuánto. Antes el sistema podía omitir ese dato sin avisar. Ahora queda pendiente y no se suma. Cuando la persona confirma 100.000 pesos, el gasto total pasa a 180.000 y el saldo a 1.320.000.”

**2:50–3:10:** regresar al pitch.

“Si no sabemos el monto, podemos excluirlo explícitamente y aceptar un resumen parcial. Nunca queremos convertir una duda en una cifra aparentemente segura.”

## 3:10–4:00 · Arquitectura AI native · Miguel

“El flujo empieza en texto libre. Gemini devuelve movimientos estructurados, categorías y citas literales. El servidor valida el esquema, detecta pendientes y muestra la revisión humana. Después Python suma, calcula el saldo y valida el resultado. La IA es necesaria para interpretar el lenguaje variable que alimenta el producto; la aritmética está separada. Una cita presente no demuestra por sí sola que el monto se interpretó bien, así que la persona siempre revisa. Retiramos las recomendaciones numéricas libres: el escenario actual parte de gastos que el usuario selecciona.”

## 4:00–4:45 · Evals · Sebastián

“En la suite original pasamos de cuatro a cinco casos aprobados, aunque dos entradas del baseline eran equivalentes y no idénticas. Al ampliar a once, la ejecución histórica de Gemini aprobó ocho. Los tres fallos mostraron que los números podían cuadrar sin comunicar incertidumbre. Hoy tenemos once de once pruebas offline con extracciones manuales y pruebas de regresión para cálculo, revisión y errores. Eso verifica el software; no significa once de once en Gemini. La nueva evaluación real requiere configurar la clave y repetir los once casos tres veces.”

Si ya se ejecutó la suite real, sustituir únicamente la última frase por el score real y su modelo/fecha. Conservar los fallos, si los hubo; no extrapolar un resultado offline.

## 4:45–5:15 · Gates · Sebastián

“Definimos gates técnicos de contrato, cálculo, incertidumbre, confirmación y manejo de errores; están verificados localmente. Propusimos otro gate de calidad del modelo y uno de utilidad con usuarios, ambos pendientes de evidencia. No recibimos la rúbrica oficial, por lo que estos criterios son nuestra propuesta verificable, no una aprobación atribuida al profesor.”

## 5:15–6:00 · Cierre · Sebastián

“El siguiente paso es probar con cinco personas las mismas tareas en una hoja de cálculo y en SpendWise, alternando el orden. Mediremos tiempo, errores finales y si comprenden el saldo y los pendientes. Nuestro criterio propuesto es que al menos cuatro completen el flujo y reducir veinte por ciento el tiempo mediano sin aumentar errores. Todavía es un objetivo, no un resultado. SpendWise busca facilitar la organización de gastos sin delegar decisiones de dinero: la IA interpreta, el código verifica y tú decides.”

## Preparación y contingencia

1. Ejecutar `python verify.py`; revisar el reporte.
2. Para demo real, configurar Gemini y ejecutar evals reales antes de la clase. No hacer 33 llamadas durante el pitch.
3. Abrir app y presentación en pestañas separadas. Cargar ejemplo normal; verificar zoom, conexión y permisos.
4. Ensayar una vez con cronómetro y otra vez intercambiando expositores.
5. Ante timeout/cuota, mostrar el error y cambiar explícitamente a modo ensayo. No esperar 40 segundos dos veces en una exposición de seis minutos.
6. Conservar una descarga JSON real, si existe, y reportes. Las capturas offline deben rotularse “ensayo simulado”.

## Preguntas previsibles

**¿Por qué no Excel?** Excel calcula bien; nuestra hipótesis de valor está en convertir texto informal a registros revisables. La comparación con Excel sigue pendiente.

**¿Cómo saben que la IA no inventa?** Validamos esquema/citas, comparamos inventarios en evals y exigimos revisión humana. No garantizamos ausencia universal de alucinaciones.

**¿Qué pasa con USD o devoluciones?** Se señalan y excluyen. No hay tasa automática ni conciliación bancaria.

**¿El 11/11 mide Gemini?** No: mide software con fixtures. El último resultado histórico de Gemini es 8/11 hasta que se registre una ejecución nueva.

**¿Está listo para producción?** No. Esta entrega es local y académica; falta evaluación real actual, prueba de utilidad y operación segura para despliegue público.
