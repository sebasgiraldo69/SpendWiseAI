# SpendWise AI

Web app académica para convertir gastos en lenguaje natural en un presupuesto revisable. **La IA interpreta, el código calcula y la persona confirma.**

## Abrir la aplicación

Requiere Python 3.10 o superior. La aplicación usa la biblioteca estándar: no hay dependencias obligatorias que instalar.

```powershell
python app.py
```

Abre **http://127.0.0.1:8000**. La presentación está en **http://127.0.0.1:8000/pitch**: siete diapositivas, temporizador de seis minutos y opción de imprimir o guardar como PDF.

El modo **Ensayo** funciona sin internet con once ejemplos predefinidos. Las extracciones son fixtures escritos manualmente, no respuestas reales de una IA. Para editar texto libre, usa el modo Gemini.

## Usar Gemini

```powershell
python app.py --ask-key
```

Pega la API key en la entrada oculta de la terminal, nunca en el chat ni en archivos del repositorio. Solo se conserva en memoria del proceso. También se admite la variable de entorno `GEMINI_API_KEY`.

El modelo configurado por defecto es `gemini-3.5-flash-lite`, conservando la configuración histórica del equipo. Su disponibilidad con esta cuenta no ha sido comprobada. Si corresponde, cambia `GEMINI_MODEL` antes de arrancar:

```powershell
$env:GEMINI_MODEL = 'nombre-del-modelo-disponible-en-tu-cuenta'
python app.py --ask-key
```

Selecciona **Gemini · interpretación real** y autoriza el envío del texto al proveedor. Se hace una llamada de extracción por solicitud, sin reintentos automáticos que consuman cuota. La aplicación muestra errores de clave, modelo, cuota, respuesta inválida y tiempo de espera. No cambia a simulación silenciosamente.

Integración basada en la [documentación oficial de salidas estructuradas de Gemini](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en). Consulta el [catálogo oficial](https://ai.google.dev/gemini-api/docs/models) para disponibilidad de modelos.

## Flujo de uso

1. Pega ingresos y gastos del mismo mes, o carga un ejemplo.
2. Revisa el ingreso, cada monto, categoría y cita de origen.
3. Completa los datos dudosos o excluye explícitamente los movimientos. Monedas extranjeras y devoluciones se excluyen y deben conciliarse fuera del presupuesto; no se convierten ni se restan automáticamente.
4. Opcionalmente, selecciona gastos para simular una reducción del 10%. El ahorro se calcula con código a partir de esa selección; no es una promesa del modelo.
5. Confirma la revisión y consulta el resumen. Puedes volver a corregir y descargar el JSON, identificado como simulado o real.

Ingreso ausente → saldo y porcentaje `null`. Ingreso cero → porcentaje `null`. Una categoría desconocida se muestra como `otros`, conserva el importe y exige revisión. Los montos usan hasta dos decimales, redondeo decimal HALF_UP y límite de un billón de COP.

## Comprobar el proyecto

```powershell
python verify.py
python -m unittest discover -s tests -v
python -m evals.run_evals --output evals/offline_report.json
```

`verify.py` ejecuta pruebas e invariantes y genera `evals/gates_report.json`. Su código de salida refleja solo los gates técnicos; `all_gates_pass` permanece falso mientras falten evidencias externas.

Para evaluar el modelo real, se requieren 33 llamadas (11 casos × 3 repeticiones), sujetas a cuota y costo de la cuenta:

```powershell
python -m evals.run_evals --live --ask-key --repeat 3 --output evals/runs/live.json
```

Los reportes registran modelo, versión del prompt, hashes de código/dataset, resultados individuales, extracción, incidencias, latencia y consumo de tokens cuando el proveedor lo informa. No contienen la clave. Los casos son sintéticos.

## Evidencia y límites

- Histórico original: **4/5 → 5/5**; no todos los textos del baseline eran idénticos a los de la suite versionada.
- Última suite histórica con Gemini: **8/11**. Falló comunicar gasto sin monto, devolución y categoría ambigua.
- Suite actual offline: **11/11 con fixtures manuales**. Esto prueba el software, no la calidad de Gemini.
- Nueva evaluación real de Gemini: **pendiente por credencial no configurada**.
- Pruebas con usuarios y rúbrica oficial: **pendientes**; no se inventaron entrevistas, métricas ni aprobaciones.

Una cita existente demuestra procedencia textual, pero no garantiza que el monto o la categoría se hayan interpretado correctamente. Las reglas de respaldo para incertidumbre cubren expresiones concretas, no todo el lenguaje español. Por eso siempre hay revisión humana.

## Entregables

| Archivo | Contenido |
|---|---|
| `app.py`, `web/` | Web app local y presentación navegable |
| `spendwise_service.py` | Extracción estructurada, validación, incidencias y revisión |
| `spendwise_core.py` | Cálculos, escenarios y contrato determinista |
| `SpendWiseAI.ipynb` | Notebook actualizado para explorar y ejecutar evals |
| `docs/SpendWiseAI_historico.ipynb` | Notebook original preservado con outputs históricos |
| `docs/arquitectura.md` | Flujo real, fronteras y decisiones |
| `docs/gates.md` | Criterios propuestos, evidencia y pendientes |
| `docs/pitch_6_minutos.md` | Guion cronometrado para dos integrantes y plan de demo |
| `docs/SpendWiseAI_pitch.pdf` | Siete diapositivas listas para presentar |
| `docs/validacion_usuarios.md` | Protocolo y plantilla de resultados sin fabricar evidencia |
| `evals/` | Casos, fixtures, runner y reportes |
| `tests/` | Regresiones de dominio, servicio y HTTP |

La prueba opcional `python tests/browser_smoke.py` requiere Playwright y Microsoft Edge instalados. No es una dependencia de la aplicación. Verifica los once ejemplos, correcciones, exportación, pantalla móvil y pitch; genera capturas en `artifacts/browser/` y el reporte `evals/browser_report.json`.

## Privacidad y alcance

Servidor enlazado solo a `127.0.0.1`, pensado para demostración local. No es un despliegue público: no incluye cuentas, autenticación de usuarios, base de datos ni controles operativos de producción. Las revisiones permanecen en memoria hasta 30 minutos, se eliminan al iniciar un nuevo presupuesto y desaparecen al detener el servidor. No se registran entradas ni claves en logs. La descarga JSON es una decisión explícita del usuario y puede contener datos financieros.

En modo Gemini el texto se envía al proveedor. La retención del proveedor está fuera del control de este prototipo; usa datos ficticios para la exposición. No hay conexión bancaria ni decisiones automáticas sobre dinero.

## Autores

Sebastián Giraldo Franco y Miguel Ángel Zuleta Zuleta · Makers AI Product.
