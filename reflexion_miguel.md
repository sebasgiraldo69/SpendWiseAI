# Reflexión — Miguel Ángel

## Aporte individual

Mi aporte parte de una pregunta distinta a la de los totales: antes de sumar,
¿podemos confiar en los movimientos que se extrajeron? Agregué
`review_extracted_movements`, que marca descripciones vacías, valores inválidos,
categorías fuera del contrato y líneas repetidas con el mismo monto. La función
no elimina movimientos ni los corrige: devuelve la razón y exige confirmación
cuando podría haber un duplicado real.

También añadí seis casos de evaluación sobre transferencias ambiguas, retiros de
efectivo, devoluciones, ingreso cero, formatos inválidos y duplicados idénticos.
Son casos donde una suma correcta puede seguir describiendo una realidad
financiera incorrecta.

## Riesgo que sigue abierto

Un duplicado exacto no siempre es un error: alguien puede pagar dos taxis
iguales. Por eso el guardrail no intenta adivinar; detiene la recomendación y
pide una decisión al usuario. El siguiente experimento debería medir si esa
confirmación reduce correcciones posteriores sin volver el flujo demasiado
lento.
