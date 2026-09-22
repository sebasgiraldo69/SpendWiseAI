# Gates propuestos para la entrega

Estos criterios los propone el equipo para hacer revisable el prototipo. No se recibió una rúbrica oficial y no representan aprobación del profesor. Separamos controles comprobables de evidencia aún pendiente.

| Gate | Criterio de aprobación | Evidencia | Estado actual |
|---|---|---|---|
| T1 · Contrato y números | Todas las pruebas de montos, sumas, saldo, porcentaje, tipos y ahorro pasan; ninguna cifra sin soporte se acepta | `tests/test_spendwise.py`, `evals/gates_report.json` | Verificado localmente |
| T2 · Incertidumbre y humano | Datos incompletos/dudosos visibles; no generar resultado sin confirmación; permitir corregir; no sumar devolución ni USD | Pruebas de servicio y demo web | Verificado localmente |
| T3 · Errores y acceso local | Cuota, timeout y JSON inválido bloquean; clave no expuesta; rutas arbitrarias y origen externo rechazados | Tests de proveedor simulado y HTTP | Verificado localmente; no auditoría de seguridad |
| T4 · Regresión | 11/11 casos offline, inventario completo y expectativas explícitas | `evals/offline_report.json` | PASS con fixtures manuales |
| E1 · Calidad de Gemini | 11 casos × 3 repeticiones = 33/33; cero movimientos inventados/omitidos, totales incorrectos o incertidumbre no comunicada | Nuevo reporte `--live --repeat 3`, modelo, prompt y hashes | PENDIENTE: falta clave configurada |
| E2 · Valor para usuarios | 5 usuarios; al menos 4 completan el flujo; mediana del tiempo 20% menor frente a hoja de cálculo, sin aumento de errores finales | `docs/validacion_usuarios.md` + resultados reales | PENDIENTE: no se hicieron pruebas |
| E3 · Requisitos del curso | Mapear estos entregables a todos los gates oficiales | Rúbrica o confirmación del profesor | PENDIENTE: no disponible |

## Cómo reproducir

```powershell
python verify.py
python -m evals.run_evals --live --ask-key --repeat 3 --output evals/runs/live.json
```

`verify.py` no llama a Gemini. Un exit code 0 significa que pasaron los gates técnicos, no que se aprobaron E1–E3. El JSON conserva `all_gates_pass: false`. Los estados externos no se promueven automáticamente: requieren revisión de la evidencia.

## Qué se considera fallo crítico

- Movimiento inventado, omitido o con monto incorrecto frente al inventario anotado.
- Sumar monedas diferentes sin tasa confirmada, o restar una devolución no conciliada.
- Entregar un saldo o porcentaje incorrecto, NaN, infinito o dividir por cero.
- Presentar presupuesto definitivo sin revisión humana.
- Declarar ahorro potencial sin escenario trazable a movimientos confirmados.
- Ocultar pendientes o presentar simulación como llamada real al modelo.

El evaluador actual compara inventario, ingreso, gasto, controles y contrato, además de los valores específicos de cada caso. En los casos que piden ausencia de invención, la evidencia es el inventario anotado; buscar una palabra en el texto ya no basta. Las etiquetas similares de categorías o anotaciones discutibles deben resolverse en el dataset y documentarse, nunca ajustarse solo para subir el score.

## Presentación y demo

La exposición debe mostrar una entrada normal y una incompleta, revisión humana, presupuesto, diagrama y separación de resultados históricos/offline/live. La presentación está en `/pitch`; el guion suma exactamente seis minutos. La validación de duración requiere ensayo real del equipo; el temporizador facilita medirla.

## Decisión de entrega

Apto para ensayar y demostrar el flujo local con datos sintéticos. No se afirma aprobación total de gates, confiabilidad de producción ni mejora real de Gemini hasta ejecutar E1. Si E1 falla, registrar el caso, cambiar una hipótesis a la vez y repetir; conservar el reporte fallido para trazabilidad.
