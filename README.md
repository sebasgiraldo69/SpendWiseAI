# SpendWise AI

Proyecto académico desarrollado para la materia **Makers AI Product**.

SpendWise AI es un asistente que ayuda a estudiantes universitarios y jóvenes profesionales a entender en qué gastan su dinero. Recibe un ingreso mensual y una lista de gastos, organiza los movimientos, calcula el estado general del presupuesto y propone oportunidades de ahorro basadas únicamente en la información suministrada.

## Objetivo

Convertir una lista de gastos escrita en lenguaje natural en un resultado financiero claro y estructurado que posteriormente pueda ser utilizado como JSON.

El sistema no debe inventar gastos, ingresos ni información financiera. Las recomendaciones son orientativas y la decisión final siempre corresponde al usuario.

## Funcionalidades

El prototipo realiza el siguiente flujo:

1. Valida que exista un ingreso mensual y al menos un gasto válido.
2. Extrae la descripción y el valor de cada movimiento.
3. Clasifica los gastos en vivienda, alimentación, transporte, educación, entretenimiento u otros.
4. Calcula el gasto total, el saldo disponible y el porcentaje del ingreso gastado.
5. Identifica la categoría con mayor gasto.
6. Detecta gastos que podrían reducirse.
7. Genera oportunidades de ahorro y una recomendación principal.
8. Devuelve un resultado estructurado.

## Estructura del output

El resultado contiene exactamente los siguientes campos:

```json
{
  "ingreso_total": 0,
  "gasto_total": 0,
  "saldo_disponible": 0,
  "porcentaje_gastado": 0,
  "categorias": {},
  "categoria_mayor_gasto": null,
  "gastos_reducibles": [],
  "oportunidades_ahorro": [],
  "ahorro_potencial": 0,
  "recomendacion_principal": null,
  "estado_financiero": null
}
```

## Archivo principal

El proyecto se encuentra en el notebook:

```text
SpendWiseAI.ipynb
```

El archivo `HealthGuideAI.ipynb` corresponde al ejemplo académico utilizado como referencia estructural.

## Requisitos

- Una cuenta de Google.
- Acceso a Google Colab.
- Una clave de Gemini API creada en Google AI Studio.
- Acceso a internet para instalar las dependencias y llamar a Gemini.

El notebook instala las siguientes librerías:

```text
google-genai
gradio
pydantic
pandas
```

## Configuración en Google Colab

### 1. Abrir el notebook

Sube `SpendWiseAI.ipynb` a Google Drive y ábrelo con Google Colab.

### 2. Crear la clave de Gemini

1. Entra a [Google AI Studio](https://aistudio.google.com/apikey).
2. Crea o selecciona un proyecto.
3. Pulsa **Create API key**.
4. Copia la clave generada.

La clave es privada. No debe pegarse directamente en una celda, publicarse en GitHub ni incluirse en capturas de pantalla.

### 3. Guardar la clave en Colab

1. En la barra lateral izquierda de Colab, abre **Secretos**, identificado con el ícono de una llave.
2. Selecciona **Agregar un secreto nuevo**.
3. En el campo de nombre escribe exactamente:

```text
GEMINI_API_KEY
```

4. En el campo de valor pega la clave de Gemini.
5. Activa el interruptor que permite el acceso desde el notebook.

El notebook recupera la clave de forma segura mediante:

```python
from google.colab import userdata

GEMINI_API_KEY = userdata.get("GEMINI_API_KEY")
```

### 4. Seleccionar el modelo

La configuración debe utilizar un modelo disponible para la cuenta:

```python
MODEL = "gemini-3.5-flash-lite"
```

Si Google informa que ese modelo dejó de estar disponible, debe sustituirse por el modelo recomendado explícitamente en el mensaje de error o en la documentación actual de Gemini.

### 5. Ejecutar el notebook

Ejecuta las celdas en orden, comenzando por la celda **0. Configuración**.

Cuando la configuración termine correctamente aparecerá:

```text
✅ Entorno listo
```

No es recomendable pulsar **Ejecutar todas** repetidamente, porque cada llamada a Gemini consume cuota.

## Ejemplo de entrada

```text
Ingreso mensual: 2.800.000 COP
Arriendo: 900.000
Mercado: 350.000
Restaurantes: 300.000
Uber: 280.000
Netflix: 26.900
Spotify: 19.900
Salidas con amigos: 350.000
Universidad: 400.000
```

Para este ejemplo, los cálculos deterministas esperados son:

- Ingreso total: `2.800.000 COP`
- Gasto total: `2.626.800 COP`
- Saldo disponible: `173.200 COP`
- Porcentaje gastado: `93,81 %`

La clasificación de categorías y las recomendaciones son producidas por el componente de IA, pero deben utilizar exclusivamente los movimientos presentes en la entrada.

## División de responsabilidades

### Software determinista

- Validar la presencia del ingreso y los gastos.
- Verificar que los valores sean numéricos y válidos.
- Sumar los gastos.
- Calcular el saldo disponible.
- Calcular el porcentaje gastado.
- Validar que el output tenga los campos requeridos.

### Componente de IA

- Interpretar descripciones escritas en lenguaje natural.
- Extraer y clasificar movimientos.
- Identificar patrones de gasto.
- Detectar gastos potencialmente reducibles.
- Generar recomendaciones basadas en los datos suministrados.

### Usuario

- Revisar el resultado.
- Corregir datos ambiguos o incompletos.
- Decidir si aplica las recomendaciones sugeridas.

## Estructura académica del notebook

El notebook conserva la estructura solicitada para el laboratorio:

1. Reality check.
2. Evaluación de IA frente a software tradicional.
3. Gemini como crítico del caso.
4. Contrato mínimo del producto.
5. Visualización del flujo de IA.
6. Prototipo ejecutable.
7. Pruebas adversariales.
8. Evaluación automática del contrato.
9. Comparación de ideas.
10. Pitch de 60 segundos.

## Manejo de errores frecuentes

### `AssertionError: Agrega GEMINI_API_KEY`

El secreto no existe, su nombre no coincide o no tiene habilitado el acceso desde el notebook. Verifica que se llame exactamente `GEMINI_API_KEY`.

### `404 NOT_FOUND`

El modelo configurado ya no está disponible para la cuenta. Cambia la variable `MODEL` por el modelo que Gemini recomiende en el mismo mensaje de error.

### `429 RESOURCE_EXHAUSTED`

Se alcanzó un límite de solicitudes o de cuota. Espera el tiempo de restablecimiento y vuelve a ejecutar solamente la celda que falló.

### `503 UNAVAILABLE`

El modelo está experimentando alta demanda. Es un error temporal del servicio. Espera unos minutos o utiliza otro modelo disponible.

### `ValidationError` en `score`

Gemini puede devolver una puntuación fuera del rango de 0 a 10. Antes de validar el resultado se puede normalizar así:

```python
try:
    evaluation_raw["score"] = int(evaluation_raw.get("score", 0))
except (TypeError, ValueError):
    evaluation_raw["score"] = 0

evaluation_raw["score"] = max(0, min(evaluation_raw["score"], 10))
```

## Pruebas incluidas

El prototipo contempla casos para verificar:

- Entrada normal.
- Ausencia del ingreso mensual.
- Información contradictoria.
- Intentos de prompt injection.
- Gastos superiores al ingreso.
- Cumplimiento estricto de los campos del contrato.

## Limitaciones

- El prototipo depende de la disponibilidad y la cuota de Gemini.
- La clasificación puede requerir revisión cuando una descripción sea ambigua.
- El sistema no accede automáticamente a cuentas bancarias ni extractos.
- No ofrece asesoría de inversión, crédito, impuestos o decisiones financieras definitivas.
- Las oportunidades de ahorro son estimaciones y no garantías.

## Seguridad y privacidad

- No publiques la clave de Gemini.
- Si una clave aparece en una captura o repositorio, elimínala y crea una nueva.
- Para las pruebas académicas, evita introducir información bancaria sensible.
- Utiliza datos ficticios o anonimizados cuando sea posible.

## Entregables

El notebook permite obtener:

- Evaluación del caso de uso.
- Contrato del producto.
- Diagrama Mermaid.
- Output del caso normal.
- Tabla de pruebas adversariales.
- Resultado de la validación del contrato.
- Pitch de 60 segundos.
- Propuesta de evidencia para validar en las siguientes 48 horas.

## Autores

Proyecto desarrollado por Sebastián Giraldo Franco y Miguel Ángel Zuleta Zuleta
