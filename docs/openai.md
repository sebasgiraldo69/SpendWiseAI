# SpendWise AI con OpenAI

La versión actual usa OpenAI Responses API para interpretar gastos, explicar comparaciones y conversar sobre planes. El modelo predeterminado es `gpt-4.1-mini`; Gemini ya no participa en las llamadas de la aplicación.

## Configuración

Con el entorno virtual activado, instala las dependencias:

```powershell
python -m pip install -r requirements.txt
```

En el archivo `.env` de la carpeta del proyecto, completa:

```dotenv
OPENAI_API_KEY=pega_tu_clave_aqui
OPENAI_MODEL=gpt-4.1-mini
```

No copies la clave a archivos de código ni al navegador. `.env` está excluido de Git. `.env.example` es una plantilla sin secretos. Las variables antiguas de Gemini pueden permanecer: la aplicación no las usa. Una variable `OPENAI_API_KEY` o `OPENAI_MODEL` definida en la terminal tiene prioridad sobre `.env`.

Detén el servidor anterior con Ctrl+C y ejecuta:

```powershell
python main.py
```

Abre http://127.0.0.1:8000 y recarga con Ctrl+F5. Autoriza el envío antes de interpretar o conversar. No es necesario cambiar el modelo para iniciar.

## Integración

`ai_provider.py` centraliza las solicitudes a `https://api.openai.com/v1/responses`. Solicita JSON Schema estricto, `store=false` y un máximo de 8192 tokens de salida. Usa tiempos de espera de conexión de 5 segundos y de lectura de 35 segundos, sin reintentos ocultos. Estos son límites de operaciones de red, no una garantía de duración total ni de disponibilidad.

`services.py` mantiene los prompts y cálculos existentes. `planning.py` conserva la conversación y valida las propuestas. La aplicación no modifica los presupuestos al generar o revisar una simulación. Los mensajes de la interfaz identifican OpenAI como destinatario de los datos.

Errores de clave, permisos, modelo, cuota, timeout, respuesta incompleta y rechazo del modelo se muestran sin exponer la clave o el contenido de las solicitudes. Un error 429 requiere revisar cuota, límites o saldo del proyecto de API; cambiar el código no aumenta esa cuota.

## Validación de la migración

```powershell
python -m unittest discover -s tests -p test_openai_provider.py -q
python -m unittest discover -s tests -p test_ai_errors.py -q
python -m unittest discover -s tests -p test_planning.py -q
python tests/browser_planning.py
```

Resultado: 14 pruebas locales y recorrido de navegador aprobados con respuestas simuladas. Falta comprobar la respuesta real con una clave de OpenAI configurada. Los tests y reportes de arquitecturas anteriores no certifican esta migración.

## Documentación oficial

- [Respuestas estructuradas](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Modelo GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

Las presentaciones y documentos históricos pueden mencionar Gemini: corresponden a la implementación anterior.
