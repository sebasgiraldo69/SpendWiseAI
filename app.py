"""Start the local ASGI API: python app.py --ask-key."""
import argparse
from getpass import getpass
import os
import uvicorn
from spendwise_api import create_app

app = create_app()

def check_gemini():
    """Probe the provider with synthetic data, never saved expenses."""
    from spendwise_provider import ProviderError, generate_sync
    from spendwise_service import MODEL, call_gemini, validate_extraction
    print(f'Diagnóstico Gemini: modelo={MODEL}. Solo se envían datos ficticios.', flush=True)
    schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}
    try:
        result, meta = generate_sync('Devuelve {"ok":true}.', schema, {'prueba': True}, 'diagnostic-v1', MODEL)
        if result.get('ok') is not True:
            print('La respuesta mínima llegó, pero su contenido no fue el esperado.', flush=True)
            return 1
        print(f"Respuesta mínima OK: {meta['latency_ms']} ms.", flush=True)
    except ProviderError as exc:
        print(f'Falló la respuesta mínima: {exc.code}. {exc}', flush=True)
        if exc.code in ('gemini_500', 'gemini_502', 'gemini_503', 'gemini_504'):
            print('El servicio respondió con un error de servidor tras un reintento. Esto no identifica un problema de tu red. Si persiste, reporta el código y modelo al soporte de Gemini.', flush=True)
        elif exc.code in ('read_timeout', 'connect_timeout', 'connection_error'):
            print('No se completó la comunicación con el proveedor; este resultado no identifica por sí solo la causa.', flush=True)
        return 1
    text = 'Ingreso mensual: 1000000 COP. Mercado: 50000 COP.'
    try:
        result, meta = call_gemini(text)
        validate_extraction(result, text)
        print(f"Extracción pequeña OK: {meta['latency_ms']} ms.", flush=True)
        print('Ambas pruebas respondieron. Esto no garantiza la latencia de entradas más grandes.', flush=True)
        return 0
    except ProviderError as exc:
        print(f'Falló la extracción: {exc.code}. {exc}', flush=True)
        return 1
    except ValueError:
        print('La extracción respondió, pero no cumplió las validaciones de SpendWise.', flush=True)
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--ask-key', action='store_true')
    parser.add_argument('--model', help='Modelo Gemini para esta ejecución; prevalece sobre GEMINI_MODEL.')
    parser.add_argument('--check-gemini', action='store_true', help='Prueba Gemini con datos ficticios sin iniciar el servidor.')
    args = parser.parse_args()
    if args.model:
        import re
        import spendwise_service
        if not re.fullmatch(r'[a-zA-Z0-9._-]+', args.model):
            parser.error('Nombre de modelo inválido.')
        spendwise_service.MODEL = args.model
    if args.ask_key:
        os.environ['GEMINI_API_KEY'] = getpass('Gemini API key (oculta): ').strip()
    if args.check_gemini:
        raise SystemExit(check_gemini())
    print(f'SpendWise AI: http://127.0.0.1:{args.port}', flush=True)
    print('Clave cargada; conexión a Gemini aún no verificada.' if os.getenv('GEMINI_API_KEY') else 'Falta Gemini API key. Reinicia con --ask-key.', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)

if __name__ == '__main__':
    main()
