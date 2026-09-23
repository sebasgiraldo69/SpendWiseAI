# Gates Makers — revisión 2026-09-23

Referencia revisada: `origin/main`, integrada localmente en `makers/review`.

| Gate | Estado | Evidencia | Para cerrar |
|---|---|---|---|
| Arquitectura atribuible | PASS | `docs/arquitectura.md`; commits de Sebastián y Miguel. | Ambos deben explicar jobs, storage y frontera IA/código. |
| Uso de IA + evals | NO PASA | El reporte guardado dice 11/11 offline, pero la suite actual no recolecta: importa cuatro módulos eliminados en el refactor. | Reparar la suite, regenerar offline y luego ejecutar live sin mezclar métricas. |
| Jailbreak y safety | PARCIAL | Consentimiento y confirmación humana están diseñados. | Guardar corrida live de prompt injection y manipulación de montos. |
| Mantenibilidad | PARCIAL | Separación razonable; `services.py` supera 300 líneas. | Dividir extracción, jobs y presupuesto. |
| Producto ejecutable | PASS | API, persistencia y web. | Medir primera activación y retorno a siete días. |
| Git profesional | PARCIAL | Ambos tienen commits y está integrado a `main`; se agregó CI en `makers/review`. | Hacer pasar el CI y llevar el arreglo mediante PR propio. |

Los resultados offline prueban reglas y fixtures; no prueban por sí solos el comportamiento de Gemini.
