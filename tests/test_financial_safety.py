import unittest

from spendwise_core import review_extracted_movements, validate_financial_output


class FinancialSafetyTests(unittest.TestCase):
    def test_flags_identical_extracted_movements_for_confirmation(self):
        review = review_extracted_movements([
            {"descripcion": "Taxi aeropuerto", "valor": 75000, "categoria": "transporte"},
            {"descripcion": " taxi   aeropuerto ", "valor": 75000, "categoria": "transporte"},
        ])
        self.assertFalse(review["valid"])
        self.assertTrue(review["needs_confirmation"])
        self.assertIn("Posible gasto duplicado", " ".join(review["errors"]))

    def test_rejects_invalid_extraction_details(self):
        review = review_extracted_movements([
            {"descripcion": "", "valor": -95000, "categoria": "transferencia"},
        ])
        self.assertFalse(review["valid"])
        self.assertFalse(review["needs_confirmation"])
        self.assertEqual(3, len(review["errors"]))

    def test_validator_rejects_inconsistent_totals(self):
        output = {
            "ingreso_total": 1000000, "gasto_total": 350000,
            "saldo_disponible": 700000, "porcentaje_gastado": 35,
            "categorias": {"alimentacion": 300000},
            "categoria_mayor_gasto": "alimentacion", "gastos_reducibles": [],
            "oportunidades_ahorro": [], "ahorro_potencial": 0,
            "recomendacion_principal": None, "estado_financiero": "estable",
        }
        result = validate_financial_output(output)
        self.assertFalse(result["valid"])
        self.assertTrue(any("La suma de categorias" in error for error in result["errors"]))


if __name__ == "__main__":
    unittest.main()
