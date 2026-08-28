# Makers Review

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

<!-- MAKERS_REVIEW_2026_08_27_START -->
## Revision docente - 2026-08-27

### Lo que vimos

- Sebastian hizo un avance muy bueno: separo calculos financieros deterministas y valido totales, saldo y porcentajes.
- Documentaron baseline 4/5 -> after 5/5, que es justo el tipo de evidencia que buscamos.
- Falta aporte individual visible de Miguel Angel.
- El riesgo principal es financiero: un JSON bonito con numeros malos genera mala decision de usuario.

### Reto de hoy

Endurezcan la validacion financiera:

1. Agregar casos de gastos duplicados, ingreso faltante, saldo negativo y categoria ambigua.
2. Separar claramente que extrae el LLM y que calcula el codigo.
3. Dejar en README.md: Current score, Known failures y Next hypothesis.

### Tarea obligatoria: diagrama de arquitectura

Crear docs/arquitectura.md con un diagrama Mermaid que muestre:

`mermaid
flowchart LR
  Usuario --> TextoFinanciero
  TextoFinanciero --> ModeloExtractor
  ModeloExtractor --> MovimientoEstructurado
  MovimientoEstructurado --> CalculadoraDeterministica
  CalculadoraDeterministica --> ValidadorFinanciero
  ValidadorFinanciero --> PresupuestoSeguro
  Evals --> ValidadorFinanciero
`

Debe quedar claro que el modelo no calcula totales finales: el codigo los recalcula.

### Criterio de aceptacion

No basta con 5/5. Deben mostrar que el sistema sigue estable con casos financieros incomodos.
<!-- MAKERS_REVIEW_2026_08_27_END -->

