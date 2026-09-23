import unittest
from unittest.mock import patch

from app import check_gemini
from spendwise_provider import ProviderError


class DiagnosticTests(unittest.TestCase):
    @patch('builtins.print')
    def test_server_error_does_not_recommend_network_change(self, output):
        with patch('spendwise_provider.generate_sync', side_effect=ProviderError('Error interno', 'gemini_500')):
            self.assertEqual(check_gemini(), 1)
        messages = ' '.join(str(call) for call in output.call_args_list)
        self.assertNotIn('otra red', messages)
        self.assertIn('error de servidor', messages)

    @patch('builtins.print')
    def test_minimal_failure_stops_before_extraction(self, output):
        with patch('spendwise_provider.generate_sync', side_effect=ProviderError('Timeout', 'read_timeout')), patch('spendwise_service.call_gemini') as extract:
            self.assertEqual(check_gemini(), 1)
            extract.assert_not_called()

    @patch('builtins.print')
    def test_success_and_invalid_extraction(self, output):
        raw = {'ingreso_total': 1000000, 'fuente_ingreso': 'Ingreso mensual: 1000000 COP.',
               'movimientos': [{'descripcion': 'Mercado', 'valor': 50000, 'categoria': 'alimentacion',
                                'moneda': 'COP', 'tipo': 'expense', 'fuente': 'Mercado: 50000 COP.'}],
               'incidencias': []}
        from spendwise_core import CATEGORIES
        raw['movimientos'][0]['categoria'] = CATEGORIES[0]
        with patch('spendwise_provider.generate_sync', return_value=({'ok': True}, {'latency_ms': 10})), patch('spendwise_service.call_gemini', return_value=(raw, {'latency_ms': 20})):
            self.assertEqual(check_gemini(), 0)
            raw['fuente_ingreso'] = 'unsupported'
            self.assertEqual(check_gemini(), 1)
