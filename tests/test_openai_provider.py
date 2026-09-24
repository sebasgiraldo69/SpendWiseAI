import json
import unittest
from unittest.mock import patch
import httpx
import ai_provider as provider
import services
from planning import Answer


class OpenAITests(unittest.TestCase):
    def call(self):
        return provider.generate_structured(model='gpt-4.1-mini',input='datos ficticios',
            system_instruction='instrucciones',response_format={'schema':Answer.model_json_schema()})

    def test_response_contract_and_no_storage(self):
        calls=[]
        def handle(req):
            calls.append(req)
            return httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"reply":"Hola"}'}]}]})
        client=httpx.Client(transport=httpx.MockTransport(handle))
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('ai_provider.httpx.Client',return_value=client):
            self.assertEqual(json.loads(self.call().output_text)['reply'],'Hola')
        payload=json.loads(calls[0].content)
        self.assertEqual(str(calls[0].url),'https://api.openai.com/v1/responses')
        self.assertFalse(payload['store'])
        self.assertTrue(payload['text']['format']['strict'])
        schema=payload['text']['format']['schema']
        self.assertFalse(schema['additionalProperties'])
        self.assertFalse(schema['$defs']['Reduction']['additionalProperties'])
        self.assertEqual(set(schema['required']),set(schema['properties']))
        self.assertTrue(client.is_closed)

    def test_missing_key_does_not_send(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':''}),patch('ai_provider.httpx.Client') as client:
            with self.assertRaises(provider.ProviderFailure) as error:self.call()
            self.assertEqual(error.exception.code,'missing_key')
            client.assert_not_called()

    def test_http_errors_are_safe(self):
        for status in (400,401,403,404,429,500,503):
            client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(status,json={'error':{'message':'SECRET'}})))
            with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('ai_provider.httpx.Client',return_value=client):
                with self.assertRaises(provider.ProviderFailure) as error:self.call()
                self.assertEqual(error.exception.code,'openai_'+str(status))
                self.assertNotIn('SECRET',str(error.exception))

    def test_timeout_and_incomplete_and_refusal(self):
        def timeout(req): raise httpx.ReadTimeout('SECRET')
        cases=[(timeout,'provider_timeout'),
               (lambda req:httpx.Response(200,json={'status':'incomplete'}),'incomplete_response'),
               (lambda req:httpx.Response(200,json={'status':'completed','output':[{'type':'message','content':[{'type':'refusal'}]}]}),'provider_refusal')]
        for handler,code in cases:
            client=httpx.Client(transport=httpx.MockTransport(handler))
            with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('ai_provider.httpx.Client',return_value=client):
                with self.assertRaises(provider.ProviderFailure) as error:self.call()
                self.assertEqual(error.exception.code,code)

    def test_all_workloads_use_shared_provider(self):
        from types import SimpleNamespace
        with patch('services.generate_structured',return_value=SimpleNamespace(output_text='{}')) as generate:
            services.extract_budget_from_text('Ingreso 100 COP')
            services.explain_comparison({},[],[])
            services.interpret_scenario('Evento','event',{})
            self.assertEqual(generate.call_count,3)
            for call in generate.call_args_list:
                schema=provider.strict_schema(call.kwargs['response_format']['schema'])
                self.assertFalse(schema['additionalProperties'])
