"""OpenAI Responses API adapter shared by all AI features."""
import copy
import json
import os
from types import SimpleNamespace
import httpx

MODEL_NAME = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')


class ProviderFailure(RuntimeError):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def strict_schema(schema):
    result = copy.deepcopy(schema)
    def visit(value):
        if isinstance(value, dict):
            value.pop('default', None)
            if value.get('type') == 'object':
                value['additionalProperties'] = False
                value['required'] = list(value.get('properties', {}))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(result)
    return result


def generate_structured(*, model, input, system_instruction, response_format):
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key or key in ('tu_clave_aqui', 'tu_clave', 'pega_tu_clave_aqui'):
        raise ProviderFailure('Falta OPENAI_API_KEY. Pon tu clave en .env y reinicia el servidor.', 'missing_key')
    payload = {'model': model, 'instructions': system_instruction, 'input': input,
               'store': False, 'max_output_tokens': 8192,
               'text': {'format': {'type': 'json_schema', 'name': 'spendwise',
                                  'strict': True, 'schema': strict_schema(response_format['schema'])}}}
    try:
        # No hidden retries: the browser must receive a useful failure in time.
        with httpx.Client(timeout=httpx.Timeout(35, connect=5), follow_redirects=False) as client:
            response = client.post('https://api.openai.com/v1/responses',
                                   headers={'Authorization': 'Bearer ' + key}, json=payload)
    except httpx.TimeoutException:
        raise ProviderFailure('OpenAI no respondió a tiempo. Tu mensaje se conserva para reintentar.', 'provider_timeout') from None
    except httpx.RequestError:
        raise ProviderFailure('No se pudo conectar con OpenAI. Revisa la conexión del servidor.', 'provider_connection') from None
    if response.status_code >= 400:
        messages = {400: 'OpenAI rechazó el formato de la solicitud.',
                    401: 'OpenAI rechazó la clave. Revisa OPENAI_API_KEY en .env.',
                    403: 'Tu proyecto de OpenAI no tiene permiso para esta solicitud.',
                    404: 'El modelo de OpenAI no está disponible para este proyecto.',
                    429: 'OpenAI indicó un límite de solicitudes o cuota. Revisa el saldo y los límites de tu proyecto.'}
        raise ProviderFailure(messages.get(response.status_code, 'OpenAI no pudo completar la solicitud. Intenta más tarde.'),
                              'openai_' + str(response.status_code))
    try:
        body = response.json()
        if body.get('status') != 'completed':
            raise ProviderFailure('OpenAI no completó la respuesta. No se aplicó ningún cambio.', 'incomplete_response')
        parts = [part for item in body.get('output', []) if item.get('type') == 'message'
                 for part in item.get('content', [])]
        if any(part.get('type') == 'refusal' for part in parts):
            raise ProviderFailure('OpenAI no pudo atender esa solicitud. Reformula tu mensaje.', 'provider_refusal')
        output = ''.join(part.get('text', '') for part in parts if part.get('type') == 'output_text')
        if not isinstance(json.loads(output), dict):
            raise ValueError('Expected object')
        return SimpleNamespace(output_text=output)
    except (ValueError, KeyError, TypeError):
        raise ProviderFailure('La respuesta de OpenAI no tiene el formato esperado. Reintenta.', 'invalid_response') from None
