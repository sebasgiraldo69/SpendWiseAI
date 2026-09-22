# Makers Review

> Revisión histórica conservada. La actualización del 2026-09-22 implementa web app, revisión humana y evals estrictos. Consultar `README.md`, `docs/gates.md` y `evals/results.md` para el estado actual; el notebook original está en `docs/SpendWiseAI_historico.ipynb`.

## Que encontramos

- El proyecto tiene un caso claro: convertir gastos en lenguaje natural en un resumen financiero estructurado.
- El README separa bien software determinista, IA y decision del usuario.
- El notebook ya incluye casos adversariales y manejo de errores de Gemini.
- El riesgo principal es financiero: inventar gastos, sumar mal o recomendar sin aclarar incertidumbre.
- Falta evidencia versionada fuera del notebook para comparar baseline contra mejoras.

## Mejora aplicada

Agregue `evals/eval_cases.json` con 5 casos especificos para presupuesto:

- calculos del caso feliz;
- ingreso faltante;
- gasto duplicado ambiguo;
- prompt injection;
- saldo negativo.

Tambien agregue `evals/results.md` para que el equipo registre baseline y after.

## Por que importa

En productos financieros, la IA no debe ser la fuente de verdad de los numeros. El modelo puede interpretar texto, pero el sistema debe verificar los calculos. Estos evals fuerzan esa frontera: modelo interpreta, codigo calcula, humano decide.

## Como probarlo

1. Abrir `SpendWiseAI.ipynb`.
2. Ejecutar cada caso de `evals/eval_cases.json` con `run_prototype`.
3. Comparar el JSON contra los valores esperados.
4. Registrar resultados en `evals/results.md`.

## Tu reto

1. Core: completar baseline real para los 5 casos y poner score `X/5`.
2. Intermediate: crear `validate_financial_output(output)` que verifique campos, sumas y saldo.
3. Advanced: separar extraccion de movimientos, calculos deterministas y generacion de recomendaciones en funciones independientes.
