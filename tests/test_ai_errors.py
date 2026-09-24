import json
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
import services


class AIFailureTests(unittest.TestCase):
    def test_extraction_timeout_is_reported_without_private_details(self):
        class APITimeoutError(Exception): pass
        with patch('main.extract_budget_from_text', side_effect=APITimeoutError('SECRET')):
            with self.assertLogs('spendwise.ai', level='WARNING') as logs:
                response=TestClient(app).post('/api/extract',json={'input':'hola','mode':'live','consent':True})
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['code'],'provider_timeout')
        self.assertNotIn('SECRET',response.text+' '.join(logs.output))

    def test_no_consent_does_not_call_gemini(self):
        with patch('main.extract_budget_from_text') as extract:
            response=TestClient(app).post('/api/extract',json={'input':'hola','mode':'live','consent':False})
        self.assertEqual(response.status_code,400)
        extract.assert_not_called()

    def test_extraction_serializes_quotes(self):
        client=MagicMock();client.__enter__.return_value=client
        client.output_text='{}'
        text='Gasto "cine"\n50000 COP'
        with patch('services.generate_structured',return_value=client) as provider:
            services.extract_budget_from_text(text)
        kwargs=provider.call_args.kwargs
        self.assertEqual(json.loads(kwargs['input'])['texto_no_confiable'],text)
