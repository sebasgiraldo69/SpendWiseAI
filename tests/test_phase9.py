import unittest
import sqlite3
from decimal import Decimal
from spendwise_storage import get_connection, initialize_database, create_budget, get_budget, delete_budget
from spendwise_compare import compare_budgets
from spendwise_core import calculate_goal_scenario, calculate_event_scenario

class Phase9Tests(unittest.TestCase):
    def setUp(self):
        # Usamos base de datos en memoria para probar persistencia aislada
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON;')
        initialize_database(self.conn)
        self.profile_id = 'demo-ana-001'
        self.profile_id_2 = 'demo-carlos-002'

    def tearDown(self):
        self.conn.close()

    def test_storage_create_and_get(self):
        movements = [
            {'description': 'Mercado', 'amount': '50000.00', 'category': 'alimentacion', 'origin': 'manual'}
        ]
        b = create_budget(self.conn, self.profile_id, 2024, 1, '100000.00', movements, 'manual')
        self.assertIsNotNone(b['id'])
        
        db_b = get_budget(self.conn, b['id'], self.profile_id)
        self.assertEqual(db_b['year'], 2024)
        self.assertEqual(db_b['month'], 1)
        self.assertEqual(db_b['income'], '100000.00')
        self.assertEqual(len(db_b['movements']), 1)
        self.assertEqual(db_b['movements'][0]['description'], 'Mercado')

    def test_isolation_cross_profile(self):
        movements = [{'description': 'Test', 'amount': '100', 'category': 'otros', 'origin': 'manual'}]
        b = create_budget(self.conn, self.profile_id, 2024, 2, '200', movements, 'manual')
        
        # Profile 2 no puede leer presupuestos del Profile 1
        self.assertIsNone(get_budget(self.conn, b['id'], self.profile_id_2))
        
        # Profile 2 no puede borrar presupuestos del Profile 1
        self.assertFalse(delete_budget(self.conn, b['id'], self.profile_id_2))
        
        # Confirmamos que sigue ahí para el Profile 1
        self.assertIsNotNone(get_budget(self.conn, b['id'], self.profile_id))

    def test_budget_unique_period(self):
        movements = [{'description': 'Test', 'amount': '100', 'category': 'otros', 'origin': 'manual'}]
        create_budget(self.conn, self.profile_id, 2024, 3, '200', movements, 'manual')
        with self.assertRaises(sqlite3.IntegrityError):
            create_budget(self.conn, self.profile_id, 2024, 3, '500', movements, 'manual')

    def test_comparison_logic(self):
        b1 = {
            'id': 'b1', 'year': 2024, 'month': 1, 'income': '1000',
            'movements': [{'id': 'm1', 'description': 'Cafe', 'amount': '50', 'category': 'alimentacion'}]
        }
        b2 = {
            'id': 'b2', 'year': 2024, 'month': 2, 'income': '1200',
            'movements': [
                {'id': 'm2', 'description': 'Cafe', 'amount': '60', 'category': 'alimentacion'},
                {'id': 'm3', 'description': 'Cine', 'amount': '100', 'category': 'entretenimiento'}
            ]
        }
        
        comp = compare_budgets(b1, b2)
        self.assertEqual(comp['income_diff'], 200.0)
        self.assertEqual(comp['expense_diff'], 110.0) # 160 - 50
        self.assertEqual(comp['balance_diff'], 90.0)
        
        # Movimiento cambiado
        self.assertEqual(len(comp['movements_changed']), 1)
        self.assertEqual(comp['movements_changed'][0]['amount_diff'], 10.0)
        
        # Movimiento agregado
        self.assertEqual(len(comp['movements_added']), 1)
        self.assertEqual(comp['movements_added'][0]['description'], 'Cine')
        
    def test_comparison_same_period(self):
        b1 = {'id': 'b1', 'year': 2024, 'month': 1, 'income': '1000', 'movements': [{'id': 'm1', 'description': 'Cafe', 'amount': '50', 'category': 'alimentacion'}]}
        b2 = {'id': 'b2', 'year': 2024, 'month': 1, 'income': '1200', 'movements': [{'id': 'm2', 'description': 'Cafe', 'amount': '60', 'category': 'alimentacion'}]}
        with self.assertRaises(ValueError):
            compare_budgets(b1, b2)

    def test_goal_scenario(self):
        budget_income = 1000.0
        budget_expense = 600.0
        reductions = [{'category': 'entretenimiento', 'description': 'Ocio', 'current_amount': 100.0, 'reduce_by': 50.0}]
        target = 200.0
        
        res = calculate_goal_scenario(budget_expense, budget_income, target, reductions)
        self.assertEqual(res['total_reduced'], 50.0)
        self.assertEqual(res['remaining_gap'], 150.0)
        self.assertFalse(res['reached_target'])
        self.assertEqual(res['new_balance'], 450.0)

    def test_event_scenario(self):
        budget_income = 1000.0
        budget_expense = 600.0
        items = [
            {'description': 'Vuelo', 'estimated_amount': 150.0, 'source': 'Web'}
        ]
        
        res = calculate_event_scenario(budget_income, budget_expense, items)
        self.assertEqual(res['event_total'], 150.0)
        self.assertEqual(res['remaining_after_event'], 250.0)
        self.assertTrue(res['affordable'])

if __name__ == '__main__':
    unittest.main()
