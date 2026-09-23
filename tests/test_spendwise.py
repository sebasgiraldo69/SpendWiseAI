import copy
import json
import os
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from spendwise_core import calculate_financials, build_output, validate_financial_output, evaluate_expected
from spendwise_service import prepare_review, confirm_review, call_gemini, ProviderError
from evals.run_evals import load_cases, load_fixtures, run_suite
import app

CASES={c['id']:c for c in load_cases()}
FIXTURES=load_fixtures()

def review_for(case='budget_happy_path_totals'):
    return prepare_review(FIXTURES[case],CASES[case]['input'],{'mode':'fixture'})

def payload_for(review):
    return {'confirmed':True,'ingreso_total':review['ingreso_total'],
            'movimientos':copy.deepcopy(review['movimientos']),'selected_ids':[]}

class FinancialTests(unittest.TestCase):
    def test_happy_path_exact(self):
        result=review_for()['preview']
        self.assertEqual((result['gasto_total'],result['saldo_disponible'],result['porcentaje_gastado']),(2626800,173200,93.81))
    def test_decimal_rounding(self):
        result=calculate_financials(1,[{'valor':.1,'categoria':'otros'},{'valor':.2,'categoria':'otros'}])
        self.assertEqual(result['gasto_total'],.3)
        self.assertEqual(result['saldo_disponible'],.7)
        self.assertEqual(calculate_financials(3200000,[{'valor':1860000,'categoria':'otros'}])['porcentaje_gastado'],58.13)
    def test_null_and_zero_income(self):
        for income in (None,0):
            result=calculate_financials(income,[{'valor':50,'categoria':'otros'}])
            self.assertIsNone(result['porcentaje_gastado'])
            self.assertEqual(result['saldo_disponible'],None if income is None else -50)
    def test_invalid_numbers(self):
        for value in (True,False,float('nan'),float('inf'),-1,'500',1.001,1e13):
            with self.subTest(value=value),self.assertRaises(ValueError):
                calculate_financials(100,[{'valor':value,'categoria':'otros'}])
    def test_negative_income(self):
        with self.assertRaises(ValueError): calculate_financials(-1,[])
    def test_wrong_sum_and_savings_blocked(self):
        for field,value in [('saldo_disponible',1),('gasto_total',None),('ahorro_potencial',999999999),('gastos_reducibles','incorrecto'),('categorias',{'otros':-1}),('estado_financiero',None),('porcentaje_gastado',True)]:
            with self.subTest(field=field):
                result=copy.deepcopy(review_for()['preview']);result[field]=value
                self.assertFalse(validate_financial_output(result)['valid'])
    def test_source_checked_savings(self):
        review=review_for();payload=payload_for(review);payload['selected_ids']=['m3']
        result=confirm_review(review,payload)
        self.assertEqual(result['output']['ahorro_potencial'],30000)
        result['output']['gastos_reducibles'][0]['descripcion']='Inventado'
        self.assertFalse(validate_financial_output(result['output'],result['movimientos_confirmados'])['valid'])
    def test_unknown_savings_id(self):
        with self.assertRaises(ValueError): build_output(10,[{'id':'m1','descripcion':'Bus','valor':1,'categoria':'transporte'}],['fake'])
    def test_injection_controls_need_evidence(self):
        self.assertTrue(evaluate_expected(review_for()['preview'],{'must_ignore_injection':True,'must_not_invent_expenses':True}))
    def test_unknown_expectation_fails(self):
        self.assertTrue(evaluate_expected(review_for()['preview'],{'unknown_control':True}))

class ReviewTests(unittest.TestCase):
    def test_all_offline_evals(self):
        report=run_suite()
        self.assertEqual(report['passed'],11)
        self.assertEqual(report['mode'],'fixture')
    def test_three_historical_failures_surface(self):
        for case,code in [('budget_expense_without_amount','missing_amount'),('budget_refund_negative_value','refund'),('budget_ambiguous_category','unknown_category')]:
            with self.subTest(case=case):
                review=review_for(case)
                self.assertIn(code,[i['codigo'] for i in review['incidencias']])
                self.assertTrue(review['requires_confirmation'])
    def test_omitted_uncertainty_still_flagged(self):
        for case,code in [('budget_expense_without_amount','missing_amount'),('budget_refund_negative_value','refund')]:
            raw=copy.deepcopy(FIXTURES[case]);raw['movimientos']=[m for m in raw['movimientos'] if m['valor'] is not None and m['tipo']=='expense']
            review=prepare_review(raw,CASES[case]['input'])
            self.assertIn(code,[i['codigo'] for i in review['incidencias']])
    def test_human_confirmation_enforced(self):
        review=review_for();payload=payload_for(review);payload['confirmed']=False
        with self.assertRaises(ValueError): confirm_review(review,payload)
    def test_preview_does_not_claim_confirmation(self):
        self.assertIn('provisional',review_for()['preview']['estado_financiero'])
        self.assertTrue(review_for()['human_review_required'])
    def test_missing_amount_correction(self):
        review=review_for('budget_expense_without_amount');payload=payload_for(review)
        payload['movimientos'][0].update(valor=100000,incluir=True)
        result=confirm_review(review,payload)
        self.assertEqual(result['output']['gasto_total'],180000)
        self.assertEqual(result['corregidos'],['m1'])
    def test_category_correction(self):
        review=review_for('budget_ambiguous_category');payload=payload_for(review)
        payload['movimientos'][0]['categoria']='educacion'
        self.assertEqual(confirm_review(review,payload)['output']['categorias']['educacion'],120000)
    def test_foreign_currency_and_refund_cannot_be_summed(self):
        for case in ('budget_mixed_currencies','budget_refund_negative_value'):
            review=review_for(case);payload=payload_for(review);payload['movimientos'][1]['incluir']=True
            with self.assertRaises(ValueError): confirm_review(review,payload)
    def test_duplicate_exclusion(self):
        review=review_for('budget_duplicate_ambiguous_rent');payload=payload_for(review)
        payload['movimientos'][1]['incluir']=True
        result=confirm_review(review,payload)
        self.assertEqual(result['output']['gasto_total'],1150000)
        self.assertEqual(result['excluidos'],['m1'])
    def test_no_silent_dropped_rows(self):
        review=review_for();payload=payload_for(review);payload['movimientos'].pop()
        with self.assertRaises(ValueError): confirm_review(review,payload)
    def test_no_empty_budget(self):
        review=review_for();payload=payload_for(review)
        for m in payload['movimientos']:m['incluir']=False
        with self.assertRaises(ValueError): confirm_review(review,payload)
    def test_quote_provenance(self):
        raw=copy.deepcopy(FIXTURES['budget_happy_path_totals']);raw['movimientos'][0]['fuente']='Inventado'
        with self.assertRaises(ValueError):prepare_review(raw,CASES['budget_happy_path_totals']['input'])
    def test_malformed_extraction(self):
        for raw in ([],{}, {'ingreso_total':0}):
            with self.assertRaises(ValueError):prepare_review(raw,'texto')

if __name__=='__main__':unittest.main()
