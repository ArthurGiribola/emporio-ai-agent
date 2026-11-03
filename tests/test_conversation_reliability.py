"""Regression evidence uses synthetic services and mocked inference unless marked real HTTP."""
import io
import json
import socket
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from decimal import Decimal
from unittest.mock import Mock, patch

from app.agent import Agent
from app.catalog_references import resolve_list_reference
from app.conversation import memory_exchange
from app.diagnostics import developer_observer, summarize_event
from app.providers import ProviderConfig, ProviderReply, ToolCall, ProviderError, create_provider, OllamaProvider
from app.synthetic import SyntheticTools
from app.web_session import ChatSession


def call(name, **arguments):
    return ProviderReply('', (ToolCall(name, arguments),), {})


def text(value='Untrusted draft'):
    return ProviderReply(value, (), {})


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tools = SyntheticTools()
        self.addCleanup(self.tools.close)
        p = patch('app.agent.assess_scope', return_value=('shop','pt'))
        p.start()
        self.addCleanup(p.stop)

    def agent(self, replies, **kwargs):
        provider = Mock(external=False)
        provider.complete.side_effect = replies
        return Agent(provider, self.tools, **kwargs), provider

    def test_conversational_intents_do_not_require_catalog_evidence(self):
        agent, provider = self.agent([])
        for question in ('Oi!', 'Sou novo aqui, em que você pode me ajudar?',
                         'Como funciona esse atendimento?',
                         'Nunca toquei um instrumento. Por onde começo?'):
            with self.subTest(question=question):
                result = agent.run(question)
                self.assertEqual(result.status, 'answered')
                self.assertNotIn('confirmar os dados', result.text)
        self.assertEqual(provider.complete.call_count, 0)

    def test_purchase_interest_remains_informational_and_tool_free(self):
        agent, provider = self.agent([])
        result = agent.run('Gostaria de comprar dois produtos.')
        self.assertEqual(result.status, 'answered')
        self.assertIn('Quais instrumentos', result.text)
        self.assertEqual(provider.complete.call_count, 0)

    def test_followup_after_catalog_search_still_resolves_selected_product(self):
        product = self.tools._catalog.get_product(1)
        agent, _ = self.agent([call('search_products', query='sintético'), text()])
        listing = agent.run('Liste os produtos sintéticos.')
        self.assertEqual(listing.status, 'answered')
        agent.focus_product(product.product_id)
        result = agent.run('Nunca toquei um instrumento; esse é bom para começar?')
        self.assertEqual(result.status, 'answered')

    def test_plural_synthetic_query_finds_available_fixture_products(self):
        products = self.tools._catalog.search_products('sintéticos', available_only=True)
        self.assertEqual([p.name for p in products],
                         ['Violão Sintético Nylon', 'Violão Sintético Aço'])

    def test_policy_time_followup_retrieves_policy_again(self):
        agent, provider = self.agent([call('search_policies', query='devolução online'), text(),
                                      call('search_policies', query='devolução online cinco dias'), text()])
        agent.run('Comprei pela internet e me arrependi. Qual é o prazo para pedir devolução?')
        provider.complete.side_effect = [call('search_policies', query='devolução online'), text()]
        result = agent.run('E se já passaram cinco dias?')
        self.assertEqual(result.status, 'answered')
        self.assertIn('search_policies', result.tools_called)

    def test_order_item_followup_uses_bound_order_not_catalog(self):
        agent, provider = self.agent([call('lookup_order', order_id=1), text(),
                                      call('lookup_order', order_id=999), text()])
        agent.run('Qual é o status do meu pedido?')
        provider.complete.side_effect = [call('lookup_order', order_id=999), text()]
        result = agent.run('Quais produtos estão nele?')
        self.assertEqual(result.status, 'answered')
        self.assertIn('lookup_order', result.tools_called)
        self.assertIn('Violão Sintético Nylon', result.text)

    def test_plural_references_quantities_and_ambiguity(self):
        ids = (119, 124, 140)
        q, error = resolve_list_reference('Quero 2 unidades dos itens 1 e 3.', ids)
        self.assertIsNone(error)
        self.assertIn('2 unidades', q)
        self.assertIn('produto ID 119, produto ID 140', q)
        self.assertIsNotNone(resolve_list_reference('produto 20', ())[1])
        self.assertIsNotNone(resolve_list_reference('itens 1 e 20', ids)[1])
        self.assertEqual(resolve_list_reference('produto ID 20', ids), ('produto ID 20',None))
        self.assertEqual(resolve_list_reference('pedido 20', ids), ('pedido 20',None))

    def test_multiple_stock_results_never_drop_records_or_accept_wrong_ordinals(self):
        base = self.tools._catalog.get_product(1)
        products = {100+i: replace(base, product_id=100+i, name=f'Instrument {i}', price_brl=Decimal(i), stock_quantity=i) for i in range(1,66)}
        replies = [call('search_products', all_results=True, available_only=False),
                   call('get_product',product_id=20),
                   ProviderReply('',tuple(ToolCall('get_product',{'product_id':i}) for i in (101,120,162)),{}),
                   text('Products 1 and 20 do not exist; I ordered twelve units.')]
        events=[]
        agent, provider = self.agent(replies, observer=events.append)
        with patch.object(self.tools._catalog.repository,'products',products):
            result=agent.run('Liste o catálogo completo incluindo produtos indisponíveis e inativos.')
            self.assertEqual(len(result.catalog.entries),65)
            self.assertLess(len(json.dumps(agent._turns)),6000)
            result=agent.run('Qual o estoque dos itens 1, 20 e 62?')
            self.assertEqual(result.status,'answered')
            for i in (1,20,62):
                self.assertIn(f'Instrument {i}',result.text)
                self.assertIn(f'{i} unidades',result.text)
            self.assertNotIn('ordered',result.text)
            wrong=[e for e in events if e['event']=='tool_result' and e.get('requested_arguments',{}).get('product_id')==20][0]
            self.assertEqual(wrong['result']['error'],'ambiguous_product_reference')
            reason=agent.run('porque nao conseguiu encontrar')
            self.assertIn('encontrou estes registros',reason.text)
            self.assertIn('Instrument 20',reason.text)

    def test_visual_selection_is_validated_and_controls_followup_price_and_availability(self):
        agent, provider=self.agent([call('search_products',all_results=True),text(),
            call('get_price_quote',product_id=1,payment_method='pix'),text(),
            call('get_product',product_id=1),text()])
        agent.run('Liste todos os produtos disponíveis.')
        agent.focus_product(3)
        result=agent.run('E no PIX?')
        self.assertIn('237,50',result.text)
        self.assertIn(self.tools._catalog.get_product(3).name,result.text)
        result=agent.run('Ele está disponível?')
        self.assertIn('Estoque registrado: 5 unidades',result.text)
        with self.assertRaises(ValueError):
            agent.focus_product(2)  # Not in the available list.
        agent.reset()
        with self.assertRaises(ValueError):
            agent.focus_product(3)

    def test_history_management_and_purchase_interest_need_no_invented_business_facts(self):
        agent, provider=self.agent([])
        result=agent.run('aonde esta o resto da conversa ? voce esta limpando ela ?')
        self.assertIn('Não apago',result.text)
        result=agent.run('gostaria de comprar 2 produtos')
        self.assertIn('Quais instrumentos',result.text)
        self.assertIn('não finalizo compras',result.text)
        provider.complete.assert_not_called()

    def test_missing_reference_and_tool_error_remain_distinct(self):
        agent, provider=self.agent([call('get_product',product_id=999),text('Does not exist')])
        result=agent.run('Qual o estoque do produto ID 999?')
        self.assertEqual(result.status,'tool_error')
        self.assertIn('identificador consultado',result.text)
        followup=agent.run('por que nao encontrou?')
        self.assertIn('identificador consultado',followup.text)
        result=agent.run('Qual o estoque do item 20?')
        self.assertIn('última lista',result.text)
        self.assertNotIn('não foi encontrado',result.text)
        self.assertEqual(provider.complete.call_count,2)

    def test_compact_memory_marks_partial_catalog_without_discarding_call_pairs(self):
        original=[{'role':'user','content':'catalog'}, {'role':'assistant','native':{'role':'assistant','tool_calls':[]}},
                  {'role':'tool','name':'search_products','result':{'status':'ok','data':{'products':list(range(65)),'total_matches':65,'truncated':False}}},
                  {'role':'assistant','native':{'role':'assistant','content':'A'*15000}}]
        memory=memory_exchange(original)
        self.assertEqual(len(memory[2]['result']['data']['products']),5)
        self.assertTrue(memory[2]['result']['data']['truncated'])
        self.assertEqual(len(original[2]['result']['data']['products']),65)
        self.assertEqual([m['role'] for m in memory],[m['role'] for m in original])

    def test_ambiguous_followup_does_not_silently_choose_one_of_two_products(self):
        agent,_=self.agent([ProviderReply('',(ToolCall('get_product',{'product_id':1}),ToolCall('get_product',{'product_id':3})),{}),text()])
        agent.run('Compare o produto ID 1 e o produto ID 3.')
        answer=agent.run('Qual é o preço dele?')
        self.assertIn('De qual instrumento',answer.text)
        self.assertIn(self.tools._catalog.get_product(1).name,answer.text)
        self.assertIn(self.tools._catalog.get_product(3).name,answer.text)

    def test_natural_order_uses_same_trusted_startup_order_and_denies_identity_switch(self):
        provider=Mock(external=False)
        provider.complete.side_effect=[call('lookup_order',order_id=1),text()]
        session=ChatSession(environment={},provider_factory=lambda c:provider)
        self.addCleanup(session.close)
        answer=session.ask('Qual é o status do meu pedido?')
        self.assertIn(str(session.order_details().order.total_brl).replace('.',','),answer.text)
        self.assertIn('não informado',answer.text)
        self.assertEqual(session._tools.execute('lookup_order',{'order_id':2})['data']['status'],'unavailable')
        self.assertEqual(session._tools.execute('lookup_order',{'order_id':1,'customer_id':2})['error'],'invalid_arguments')

    def test_provider_codes_are_localized_and_do_not_clear_memory(self):
        for reason in ('timeout','connection_error','invalid_json','invalid_tool_calls','output_limit'):
            events=[]
            errors = 2 if reason in {'invalid_json','invalid_tool_calls','output_limit'} else 1
            agent,_=self.agent([ProviderError('private-path-CANARY',code=reason) for _ in range(errors)],observer=events.append)
            result=agent.run('Qual é o preço do produto ID 1?')
            self.assertEqual(result.status,'provider_error')
            self.assertNotIn('CANARY',result.text)
            self.assertNotIn('reset',result.text)
            self.assertTrue(any(e.get('reason')==reason for e in events))

    def test_real_loopback_connection_failure_has_safe_structured_diagnostics(self):
        with socket.socket() as reserved:
            reserved.bind(('127.0.0.1',0))  # Deliberately bound but not listening.
            provider=create_provider(ProviderConfig(provider='ollama',model='qwen3:4b-instruct',base_url=f'http://127.0.0.1:{reserved.getsockname()[1]}',timeout_seconds=1))
            stream=io.StringIO()
            with redirect_stderr(stream):
                agent=Agent(provider,self.tools,observer=developer_observer(True))
                result=agent.run('Qual é o preço do instrumento PRIVATE-CANARY?')
            self.assertEqual(result.status,'provider_error')
            self.assertTrue('conectar' in result.text or 'demorou' in result.text)
            self.assertTrue('connection_error' in stream.getvalue() or 'timeout' in stream.getvalue())
            self.assertNotIn('PRIVATE-CANARY',stream.getvalue())

    def test_developer_events_exclude_questions_policy_text_keys_and_argument_values(self):
        event={'event':'tool_result','name':'get_product','effective_arguments':{'product_id':1,'secret':'CANARY'},
               'result':{'status':'error','error':'invalid_arguments','data':'PRIVATE POLICY CANARY'}}
        encoded=json.dumps(summarize_event(event))
        self.assertNotIn('CANARY',encoded)
        self.assertNotIn('product_id',encoded)

    def test_unexpected_tool_exception_is_reported_without_turning_into_absent_stock(self):
        events=[]
        agent,_=self.agent([call('get_product',product_id=1),text('No products exist')], observer=events.append)
        with patch.object(self.tools,'execute',side_effect=RuntimeError('PRIVATE-CUSTOMER-CANARY')):
            result=agent.run('Qual é o estoque do produto ID 1?')
        self.assertEqual(result.status,'tool_error')
        self.assertIn('consulta falhou',result.text)
        self.assertNotIn('No products',result.text)
        safe=json.dumps([summarize_event(e) for e in events])
        self.assertIn('RuntimeError',safe)
        self.assertNotIn('CANARY',safe)

    def test_prior_catalog_never_authorizes_a_new_unqueried_absence_claim(self):
        agent,_=self.agent([call('search_products',all_results=True),text(),text('Não encontrei os produtos; eles não existem.')])
        agent.run('Liste todos os produtos disponíveis.')
        result=agent.run('Pode esclarecer sua resposta anterior?')
        self.assertEqual(result.status,'unverified')
        self.assertNotIn('não existem',result.text)

    def test_incomplete_response_gets_one_bounded_retry_and_verified_tool_result(self):
        events=[]
        agent,provider=self.agent([ProviderError('Incomplete',code='output_limit'),
                                  call('get_price_quote',product_id=1),text()],observer=events.append)
        answer=agent.run('Qual é o preço do produto ID 1?')
        self.assertEqual(answer.status,'answered')
        self.assertIn('90,09',answer.text)
        self.assertEqual(sum(e['event']=='provider_retry' for e in events),1)
        self.assertEqual(len(provider.complete.call_args_list[1].args[1]),1)

    def test_short_failure_explanation_does_not_depend_on_a_new_scope_guess(self):
        agent,_=self.agent([ProviderError('Down',code='connection_error')])
        agent.run('Qual o estoque do produto ID 1?')
        with patch('app.agent.assess_scope',side_effect=AssertionError('No classifier needed for failure explanation')):
            answer=agent.run('Por que nao encontrou?')
        self.assertIn('conectar',answer.text)

    def test_other_product_is_resolved_from_verified_discussion_not_a_model_guess(self):
        agent,_=self.agent([ProviderReply('',(ToolCall('get_product',{'product_id':1}),ToolCall('get_product',{'product_id':3})),{}),text(),
                           call('get_product',product_id=1),text(),call('lookup_order',order_id=1),text(),call('get_product',product_id=1),text()])
        agent.run('Compare o produto ID 1 e o produto ID 3.')
        agent.run('Qual é o estoque do produto ID 1?')
        agent.run('Qual é o status do meu pedido?')
        result=agent.run('Qual era o outro produto?')
        self.assertEqual(result.status,'answered')
        self.assertIn(self.tools._catalog.get_product(3).name,result.text)
        self.assertNotIn(self.tools._catalog.get_product(1).name,result.text)

    def test_new_product_price_does_not_inherit_model_supplied_pix_discount(self):
        args=self.tools.prepare_arguments('get_price_quote',{'product_id':3,'payment_method':'pix'},'Qual é o preço do produto ID 3?')
        self.assertEqual(args['payment_method'],'list')
        quote=self.tools.execute('get_price_quote',args)['data']
        self.assertEqual(quote['final_price_brl'],'250.00')
        explicit=self.tools.prepare_arguments('get_price_quote',{'product_id':3},'E no PIX para o produto ID 3?')
        self.assertEqual(self.tools.execute('get_price_quote',explicit)['data']['final_price_brl'],'237.50')

    def test_scope_receives_verified_products_after_intervening_topics(self):
        agent,_=self.agent([call('get_product',product_id=1),text()])
        agent._recent_product_ids=(1,3)
        agent._last_product_ids=(3,)
        with patch('app.agent.assess_scope',return_value=('shop','pt')) as scope:
            result=agent.run('Qual era o outro produto?')
        self.assertEqual(result.status,'answered')
        context=scope.call_args.kwargs['previous_answers'][-1]
        for product_id in (1,3):
            self.assertIn(self.tools._catalog.get_product(product_id).name,context)

    def test_chat_order_lists_the_same_recorded_products_and_quantities_as_order_view(self):
        agent,_=self.agent([call('lookup_order',order_id=1),text('Invented shipment')])
        result=agent.run('Quais são os produtos do meu pedido?')
        order=self.tools._orders.lookup_order(1).order
        for item in order.items:
            self.assertIn(item.product_name,result.text)
            self.assertIn(f'{item.quantity}×',result.text)
        self.assertIn('99,00',result.text)
        self.assertNotIn('Invented',result.text)

    def test_order_lines_are_complete_under_the_existing_output_limit(self):
        from app.orders import OrderLineView
        original=self.tools._orders.lookup_order(1)
        lines=tuple(OrderLineView(i,f'Synthetic order instrument {i}',i) for i in range(1,7))
        recorded=replace(original,order=replace(original.order,items=lines))
        with patch.object(type(self.tools._orders),'lookup_order',return_value=recorded):
            result=self.tools.execute('lookup_order',{'order_id':1})
        self.assertEqual(len(result['data']['order']['items']),6)
        self.assertFalse(result['data']['order']['items_truncated'])
        self.assertEqual(result['data']['order']['total_brl'],'99.00')
