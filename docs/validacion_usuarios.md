# Validación con usuarios · protocolo listo para ejecutar

Estado: **no ejecutado**. No hay entrevistas, participantes ni resultados reales registrados. Esta plantilla no constituye evidencia hasta realizar las sesiones.

## Hipótesis y decisión

Para estudiantes y jóvenes profesionales que registran gastos en texto, SpendWise reduce el tiempo de organizar un presupuesto sin aumentar errores finales frente a una hoja de cálculo. No estamos validando ahorro de dinero ni disposición a pagar en esta prueba.

Criterios propuestos: al menos 4 de 5 participantes completan el flujo sin intervención del equipo; tiempo mediano al menos 20% menor y sin aumento del número de errores finales respecto al baseline. Si falla, revisar la fricción observada antes de agregar funcionalidades. Cinco usuarios ofrecen evidencia exploratoria, no significancia estadística ni representatividad del mercado.

## Participantes y consentimiento

Reclutar cinco personas del segmento, sin inventar nombres ni respuestas. Identificarlas U01–U05. Explicar que es un prototipo académico, que la participación es voluntaria y que pueden retirarse. Usar gastos sintéticos; no solicitar credenciales bancarias. No grabar ni enviar texto al proveedor sin consentimiento específico.

Registrar solo tiempos, errores, respuestas y observaciones anonimizadas. Eliminar notas identificables al terminar el curso; si la universidad impone otra política, seguirla.

## Diseño comparativo

Dos herramientas: hoja de cálculo con columnas de descripción, valor y categoría, frente a SpendWise con Gemini real configurado. Si solo se usa simulación, rotular esa sesión como prueba de usabilidad del flujo, no como prueba del beneficio de IA.

Tarea A: ingreso 1.200.000; mercado 50.000; transporte 12.500. Resultado: gastos 62.500, saldo 1.137.500, porcentaje 5,21%.

Tarea B equivalente: ingreso 1.600.000; mercado 80.000; transporte 20.000. Resultado: gastos 100.000, saldo 1.500.000, porcentaje 6,25%.

Asignación sugerida: U01, U03, U05 hacen A con hoja y B con SpendWise; U02, U04 hacen A con SpendWise y B con hoja. Así se alterna orden y herramienta; documentar el pequeño desbalance de 3/2. No reutilizar los montos para que memorizar la respuesta no explique la mejora.

Después, todos resuelven en SpendWise el caso “gasto sin monto”: ingreso 1.500.000, mercado sin recordar cuánto, bus 80.000. Solo cuando la persona detecte el faltante, entregar el dato 100.000. Esperado final: gasto 180.000, saldo 1.320.000, 12%. Observar si comprende que antes era un resumen parcial.

## Sesión de 10–15 minutos

1. Preguntar cómo organiza hoy sus gastos y pedir un ejemplo de fricción, sin sugerir la respuesta.
2. Explicar el objetivo de la tarea, sin enseñar dónde hacer clic.
3. Iniciar cronómetro al mostrar la entrada; detenerlo al entregar un presupuesto que la persona considera final.
4. Registrar correcciones, ayudas del moderador, fallos del modelo y errores finales por separado. No borrar ensayos fallidos.
5. Hacer la segunda tarea y luego la de ambigüedad.
6. Preguntar: “¿Cuánto queda?”, “¿Qué dato está pendiente?”, “¿Qué revisarías antes de confiar?”, “¿Usarías esto en lugar de tu método y por qué?”

## Registro vacío

| Usuario | Modo/modelo | Orden/tareas | Tiempo hoja (s) | Tiempo SpendWise (s) | Errores hoja | Errores SpendWise | Completó sin ayuda | Entendió pendiente | Observación literal |
|---|---|---|---|---|---|---|---|---|---|
| U01 | | | | | | | | | |
| U02 | | | | | | | | | |
| U03 | | | | | | | | | |
| U04 | | | | | | | | | |
| U05 | | | | | | | | | |

Error final: movimiento faltante/inventado, monto/categoría incorrectos o saldo erróneo. Registrar por tipo y contar con la misma regla en ambas herramientas. Tiempo incluye latencia de Gemini: es parte del costo de uso.

## Análisis y reporte

- Calcular mediana de tiempos de cada herramienta.
- Reducción porcentual = `(mediana_hoja - mediana_spendwise) / mediana_hoja * 100`.
- Comparar errores totales y número de tareas terminadas sin ayuda.
- Reportar dudas, abandonos, cuotas/timeouts y diferencias por orden.
- Citar observaciones literales anonimizadas solo si existen.
- Documentar fecha, versión de código, modelo, participantes reales, datos faltantes y decisión: seguir, corregir o replantear.

No completar la tabla con ejemplos como si fueran participantes reales. Llevar al pitch únicamente resultados efectivamente observados.
