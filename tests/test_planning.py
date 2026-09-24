import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app
from planning import Answer, ChatRequest, calculate_proposal, respond
from services import calculate_financials

BUDGET = {'year':2026, 'month':9, 'income':1000,
          'movements':[{'id':'m1','description':'Cine','amount':100,'category':'entretenimiento'}]}


class PlanningTests(unittest.TestCase):
    def test_verified_decimal_totals(self):
        answer = Answer(reply='Podemos ajustar cine.', reductions=[{'movement_id':'m1','reduce_by':10.25}],
                        event_items=[{'description':'Entrada','estimated_amount':20.10}])
        result = calculate_proposal(answer, BUDGET, calculate_financials(1000,BUDGET['movements']))
        self.assertEqual(result['remaining'],890.15)
        self.assertEqual(result['saving'],10.25)

    def test_invalid_reductions_rejected(self):
        for reductions in ([{'movement_id':'unknown','reduce_by':1}],
                           [{'movement_id':'m1','reduce_by':101}],
                           [{'movement_id':'m1','reduce_by':1}]*2):
            with self.assertRaises(ValueError):
                calculate_proposal(Answer(reply='x',reductions=reductions),BUDGET,None)

    def test_no_budget_no_invented_balance(self):
        result=calculate_proposal(Answer(reply='Estimación',event_items=[{'description':'Comida','estimated_amount':10}]),None,None)
        self.assertIsNone(result['remaining'])

    def test_followup_and_budget_reach_provider(self):
        response=SimpleNamespace(output_text=json.dumps({'reply':'Mantengamos transporte sin cambios.','reductions':[],'event_items':[]}))
        req=ChatRequest(text='No puedo reducir transporte',history=[{'role':'user','content':'Quiero ahorrar'}],consent=True)
        with patch('services.generate_structured',return_value=response) as provider:
            result=respond(req,BUDGET)
        kwargs=provider.call_args.kwargs
        context=json.loads(kwargs['input'])
        self.assertEqual(context['conversacion'][0]['content'],'Quiero ahorrar')
        self.assertEqual(context['presupuesto']['resumen_calculado']['saldo_disponible'],900)
        self.assertIn('transporte',result['reply'])

    def test_api_consent_budget_and_error(self):
        client=TestClient(app)
        with patch('main.respond_to_plan') as provider, patch('main.get_budget',return_value=None):
            self.assertEqual(client.post('/api/plan/chat',json={'text':'hola'}).status_code,400)
            self.assertEqual(client.post('/api/plan/chat',json={'text':'hola','consent':True,'budget_id':'missing'}).status_code,404)
            provider.assert_not_called()
            provider.side_effect=RuntimeError('PRIVATE KEY')
            response=client.post('/api/plan/chat',json={'text':'hola','consent':True})
            self.assertEqual(response.status_code,503)
            self.assertNotIn('PRIVATE',response.text)

    def test_api_limits_and_no_writes(self):
        client=TestClient(app)
        self.assertEqual(client.post('/api/plan/chat',json={'text':'x'*2001,'consent':True}).status_code,422)
        with patch('main.respond_to_plan',return_value={'reply':'Hola','proposal':None}), patch('main.create_budget') as create, patch('main.update_budget') as update:
            self.assertEqual(client.post('/api/plan/chat',json={'text':'hola','consent':True}).status_code,200)
            create.assert_not_called(); update.assert_not_called()


if __name__=='__main__': unittest.main()
