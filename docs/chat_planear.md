# Planear como conversación

La sección Planear usa `POST /api/plan/chat` y la misma integración OpenAI Responses API que el proyecto actual. Puede conversar sin presupuesto; con un mes seleccionado recibe sus movimientos y un resumen calculado por Python. El historial incluye propuestas estructuradas anteriores para poder responder a ajustes como «no reduzcas transporte».

La memoria vive en la página: se pierde al recargar, al iniciar otra conversación o al cambiar de presupuesto. Se permiten diez intercambios por conversación. No se guarda el chat en SQLite ni en almacenamiento del navegador. Cada envío requiere consentimiento e incluye el historial y el presupuesto seleccionado. La llamada usa `store=False`; esto no sustituye las condiciones de tratamiento de datos del proveedor.

OpenAI redacta y propone. Python valida IDs de gastos, evita recortes duplicados o superiores al monto original y calcula con Decimal los ahorros, costos y saldo de la simulación. Las estimaciones de eventos son supuestos, no precios consultados. El texto libre de la IA sigue requiriendo revisión humana. «Revisar simulación» muestra el efecto calculado; no escribe cambios en el presupuesto.

Cancelar o cambiar de presupuesto descarta la respuesta en el navegador; no garantiza detener una generación ya iniciada en el proveedor. Un fallo conserva el mensaje para reenviarlo sin añadir turnos incompletos al historial.

Validación local:

```powershell
python -m unittest discover -s tests -p test_planning.py -q
python tests/browser_planning.py
```

Las seis pruebas unitarias/de API y la prueba de navegador usan respuestas simuladas, no certifican calidad o disponibilidad de OpenAI real. La prueba de navegador requiere Playwright y Edge. Ejecutar la aplicación con `python main.py` y recargar el navegador tras actualizar los archivos.

Referencia: https://developers.openai.com/api/docs/guides/structured-outputs
