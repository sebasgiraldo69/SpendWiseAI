# SpendWise AI

Aplicación local para analizar ingresos y gastos con Gemini, confirmar la interpretación, guardar presupuestos por perfil, comparar meses y planear metas o eventos.

## Ejecutar

Python 3.10 o superior. Instalar las dependencias del nuevo servidor una vez:

```powershell
python -m pip install -r requirements.txt
python app.py --ask-key
```

Pega la clave cuando la terminal la solicite (entrada oculta). Abre **http://127.0.0.1:8000**. Deja la terminal abierta.

Si tenías el servidor anterior abierto, detenlo con Ctrl+C antes de iniciar esta versión. Recarga el navegador con Ctrl+F5. El cambio de arquitectura requiere reiniciar el proceso; actualizar archivos no modifica un servidor que ya está ejecutándose.

También se admite `GEMINI_API_KEY` como variable de entorno y `python app.py --port 8001`. `GEMINI_MODEL` permite elegir un modelo disponible en la cuenta; por defecto conserva `gemini-3.5-flash-lite`. La disponibilidad de ese modelo depende del proveedor y la cuenta. No se guarda la clave en SQLite ni en el navegador.

## Flujo actual

1. Selecciona un perfil local o crea uno con **+ Perfil**.
2. Indica el periodo, escribe ingresos/gastos y autoriza el envío a Gemini.
3. Pulsa **Analizar gastos**. Puedes navegar al historial mientras el trabajo está en curso, cancelarlo o cambiar de perfil.
4. Revisa/corrige los movimientos y confirma el presupuesto. Los cálculos son deterministas en Python.
5. Guarda el mes. En **Historial** puedes verlo, editarlo o eliminarlo. Reemplazar un mes existente requiere confirmación.
6. En **Comparar**, selecciona dos meses del perfil. Las diferencias se calculan localmente; la explicación de Gemini se solicita por separado.
7. En **Planear**, selecciona un presupuesto y describe una meta o evento. Ajusta reducciones o montos, confirma los supuestos y calcula el escenario.

Ya no hay selector de ensayo ni ejemplos precargados en la aplicación. Los fixtures permanecen exclusivamente en los evals y tests. No se cambia de Gemini a simulación cuando ocurre un error.

## Arquitectura del refactor

- **FastAPI + Uvicorn:** API REST asíncrona; validación y errores HTTP consistentes.
- **HTTPX:** cliente Gemini reutilizable con conexiones persistentes, timeout de conexión de 5 s y de lectura de 25 s.
- **Trabajos de IA:** creación HTTP 202, consulta de estado, resultado y cancelación. Máximo dos llamadas simultáneas, ocho trabajos activos globales y dos por sesión. Límite total de 40 s incluyendo espera en cola.
- **SQLite:** conexión por operación, transacciones, claves foráneas y modo WAL. No se comparte una conexión mutable entre todas las solicitudes.
- **JavaScript modular:** cliente HTTP único, consultas locales limitadas a 8 s, polling cada 700 ms y descarte de respuestas de perfiles anteriores. Se bloquea el botón de la operación, no toda la interfaz.

El bloqueo previo provenía de adquirir un `threading.Lock` dentro de otro bloque que ya poseía ese mismo candado al cambiar de perfil. Esto también podía detener la limpieza del servidor. Ese mecanismo fue eliminado; las sesiones y trabajos los administra el event loop.

La API no puede garantizar que Gemini genere instantáneamente. Sí evita que su espera bloquee perfiles/historial, limita el tiempo total y permite cancelar. Hay un único reintento breve para HTTP 502/503/504; no se reintentan automáticamente cuotas, credenciales o respuestas inválidas.

Solicitudes de IA idénticas dentro de una misma sesión se deduplican hasta 120 s. Cambiar de perfil invalida trabajos y revisiones; olvidar una revisión elimina su entrada reutilizable. Los resultados de trabajo expiran a los cinco minutos. El historial tiene una caché de interfaz de diez segundos que se invalida al guardar, editar o borrar.

## API

Contrato OpenAPI: **http://127.0.0.1:8000/openapi.json**. Estado local: `/api/health`.

| Método y ruta | Uso |
|---|---|
| `GET /api/config` | Configuración y sesión local |
| `GET/POST /api/profiles` | Listar/crear perfiles |
| `POST /api/profile/select` | Cambiar perfil y cancelar trabajo anterior |
| `POST /api/extract` | Crear trabajo de extracción (202) |
| `GET/DELETE /api/jobs/{id}` | Estado/resultado o cancelación |
| `POST /api/confirm` | Confirmar datos y calcular |
| `POST /api/forget` | Descartar revisión |
| `GET/POST /api/budgets` | Historial/guardar mes |
| `GET/PUT/DELETE /api/budgets/{id}` | Leer, editar, eliminar |
| `POST /api/compare` | Comparar con datos almacenados |
| `POST /api/compare/explanation` | Trabajo de explicación (202) |
| `POST /api/scenarios/interpret` | Trabajo de meta/evento (202) |
| `POST /api/scenarios/calculate` | Calcular supuestos confirmados con el presupuesto guardado |

Los endpoints de IA devuelven un objeto con `id`, `status`, `result`, `error`. Estados: `queued`, `running`, `done`, `error`, `cancelled`. El cliente consulta el mismo ID; no repite el POST en cada consulta. Los endpoints locales no llaman a Gemini.

## Datos y compatibilidad

Se mantiene `data/spendwise.db` y el esquema existente. **No se borra el historial ni se reinician los perfiles al actualizar.** `SPENDWISE_DB_PATH` permite usar otra ubicación. El reemplazo de un presupuesto conserva su ID y actualiza sus movimientos en una transacción; si falla, los datos anteriores permanecen.

Los perfiles son locales y no equivalen a autenticación para un servicio público. El campo histórico `profile_type='demo'` permanece por compatibilidad del esquema. Las sesiones y revisiones son temporales; los presupuestos guardados sí persisten al cerrar el servidor.

Las claves no se registran. Los textos financieros solo se envían a Gemini después del consentimiento. Las revisiones se aíslan por sesión/perfil y la interfaz limpia datos anteriores al cambiar de perfil. No hay conexión bancaria, conversión de monedas ni conciliación automática de devoluciones.

## Verificar

```powershell
python verify.py
python -m unittest discover -s tests -v
python tests/benchmark_api.py
```

Prueba opcional de navegador (Microsoft Edge instalado):

```powershell
python -m pip install playwright
python tests/browser_smoke.py
```

Los tests y el benchmark usan una base temporal y un proveedor simulado inyectado solo en pruebas. No necesitan clave y no afirman medir velocidad ni calidad real de Gemini. `evals/performance_report.json` registra latencia local bajo espera simulada; `evals/browser_report.json` registra los recorridos de interfaz.

Los casos financieros offline siguen ejecutándose con:

```powershell
python -m evals.run_evals --output evals/offline_report.json
```

Para medir Gemini con once casos y tres repeticiones (33 llamadas con consumo de cuota):

```powershell
python -m evals.run_evals --live --ask-key --repeat 3 --output evals/runs/live.json
```

Los resultados históricos y los materiales académicos anteriores se conservan. Los informes nuevos distinguen pruebas simuladas de llamadas reales. El notebook mantiene su función de laboratorio; no inicia el servidor web.

## Archivos principales

`app.py`: arranque. `spendwise_api.py`: rutas y ciclo de vida. `spendwise_jobs.py`: trabajos de IA. `spendwise_provider.py`: transporte Gemini compartido por API y evals. `spendwise_service.py`: extracción y revisión. `spendwise_core.py`: números. `spendwise_storage.py`: SQLite. `spendwise_compare.py`: comparación determinista. `web/api.js`: cliente de solicitudes. `web/app.js`: interacción.

Consulta `docs/arquitectura.md` y `docs/refactor_2026-09-23.md` para las decisiones y límites.

Fuentes técnicas: [FastAPI: lifespan](https://fastapi.tiangolo.com/advanced/events/), [HTTPX: cliente asíncrono](https://www.python-httpx.org/async/), [HTTPX: timeouts](https://www.python-httpx.org/advanced/timeouts/).
