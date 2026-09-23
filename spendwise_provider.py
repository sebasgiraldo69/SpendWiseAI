"""Single Gemini transport for async API and synchronous evaluation tools."""
import asyncio
import json
import logging
import os
import re
import time
import httpx

logger = logging.getLogger(__name__)
RETRYABLE_STATUS = (500, 502, 503, 504)


def transport_error(exc, model, start):
    """Log only safe metadata: never exception text, request bodies or keys."""
    if isinstance(exc, httpx.ConnectTimeout):
        code, message = 'connect_timeout', 'No se pudo establecer la conexión con Gemini en 5 segundos. Revisa tu conexión, VPN o proxy.'
    elif isinstance(exc, httpx.ReadTimeout):
        code, message = 'read_timeout', 'La espera de datos de Gemini superó 25 segundos. Reintenta; si persiste, revisa el modelo y la conexión.'
    elif isinstance(exc, httpx.WriteTimeout):
        code, message = 'write_timeout', 'No se pudo enviar la solicitud a Gemini en 5 segundos. Revisa tu conexión.'
    elif isinstance(exc, httpx.PoolTimeout):
        code, message = 'pool_timeout', 'Las conexiones a Gemini están ocupadas. Espera unos segundos y reintenta.'
    elif isinstance(exc, httpx.TimeoutException):
        code, message = 'provider_timeout', 'La solicitud a Gemini agotó el tiempo de espera.'
    else:
        code, message = 'connection_error', 'No se pudo conectar con Gemini. Revisa tu conexión, VPN o proxy.'
    logger.warning('Gemini failure code=%s model=%s elapsed_ms=%d',
                   code, model, round((time.perf_counter() - start) * 1000))
    return ProviderError(message, code, True)

class ProviderError(RuntimeError):
    def __init__(self, message, code='provider_error', retryable=False):
        super().__init__(message)
        self.code, self.retryable = code, retryable

def request_data(prompt, schema, context, model):
    key = os.getenv('GEMINI_API_KEY', '').strip()
    if not key:
        raise ProviderError('Falta GEMINI_API_KEY. Reinicia con python app.py --ask-key.', 'missing_key')
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', model):
        raise ProviderError('GEMINI_MODEL no es válido.', 'invalid_model')
    config = {'temperature': 0, 'maxOutputTokens': 8192 if 'movimientos' in schema.get('required',[]) else 4096,
              'responseMimeType': 'application/json', 'responseJsonSchema': schema}
    # Opt-in only: model families support different thinking parameters.
    if os.getenv('GEMINI_THINKING_BUDGET'):
        config['thinkingConfig'] = {'thinkingBudget': int(os.environ['GEMINI_THINKING_BUDGET'])}
    return (f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            {'x-goog-api-key': key},
            {'systemInstruction': {'parts': [{'text': prompt}]},
             'contents': [{'role': 'user', 'parts': [{'text': json.dumps(context, ensure_ascii=False)}]}],
             'generationConfig': config})

def parse_response(response, model, version, start, attempts=1):
    if response.status_code >= 400:
        messages = {400: 'Gemini rechazó el modelo o esquema configurado.',
                    401: 'Clave de Gemini no autorizada.', 403: 'Clave de Gemini sin permisos.',
                    404: 'Modelo no disponible. Revisa GEMINI_MODEL.',
                    429: 'Cuota de Gemini agotada. Espera antes de reintentar.',
                    500: 'Gemini devolvió un error interno del servidor (500).',
                    503: 'Gemini no está disponible temporalmente. Vuelve a intentar.'}
        raise ProviderError(messages.get(response.status_code, 'Gemini no pudo completar la solicitud.'),
                            f'gemini_{response.status_code}', response.status_code in (429, *RETRYABLE_STATUS))
    try:
        raw = response.json()
        candidate = raw['candidates'][0]
        if candidate.get('finishReason') != 'STOP':
            raise ProviderError('Gemini no completó el análisis. Reduce el texto e intenta de nuevo.', 'incomplete_response')
        text = ''.join(p.get('text', '') for p in candidate['content']['parts'] if not p.get('thought'))
        result = json.loads(text)
        if not isinstance(result, dict): raise ValueError('Expected object')
        return result, {'mode': 'live', 'model': model, 'prompt_version': version,
                        'latency_ms': round((time.perf_counter()-start)*1000), 'attempts': attempts,
                        'usage': raw.get('usageMetadata', {})}
    except (ValueError, KeyError, IndexError, TypeError):
        raise ProviderError('Gemini devolvió una respuesta inválida.', 'invalid_response') from None

TIMEOUT = httpx.Timeout(connect=5, read=25, write=5, pool=2)

class GeminiClient:
    def __init__(self, model, transport=None):
        self.model = model
        self.client = httpx.AsyncClient(timeout=TIMEOUT, transport=transport,
                                       limits=httpx.Limits(max_connections=4, max_keepalive_connections=4))
    async def close(self):
        await self.client.aclose()
    async def generate(self, prompt, schema, context, version):
        url, headers, payload = request_data(prompt, schema, context, self.model)
        start = time.perf_counter()
        for attempt in range(2):
            try:
                response = await self.client.post(url, headers=headers, json=payload)
                if response.status_code in RETRYABLE_STATUS and attempt == 0:
                    await asyncio.sleep(.5)
                    continue
                return parse_response(response,self.model,version,start,attempt+1)
            except httpx.RequestError as exc:
                raise transport_error(exc, self.model, start) from None

def generate_sync(prompt, schema, context, version, model):
    url, headers, payload = request_data(prompt,schema,context,model)
    start=time.perf_counter()
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            for attempt in range(2):
                response = client.post(url, headers=headers, json=payload)
                if response.status_code in RETRYABLE_STATUS and attempt == 0:
                    time.sleep(.5)
                    continue
                return parse_response(response, model, version, start, attempt + 1)
    except httpx.RequestError as exc:
        raise transport_error(exc, model, start) from None
