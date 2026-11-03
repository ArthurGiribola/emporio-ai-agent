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
from app.conversation import memory_exchange, advisory_question, contextual_advisory_question, purchase_interest
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
                         'Como funciona esse atendimento?', 'Nunca toquei um instrumento. Por onde começo?'):
            with self.subTest(question=question):
                result = agent.run(question)
                self.assertEqual(result.status, 'answered')
                self.assertNotIn('confirmar os dados', result.text)
                self.assertEqual(result.tools_called, ())
        self.assertIn('orçamento', result.text)
        self.assertEqual(provider.complete.call_count, 0)

    def test_paraphrased_social_and_repair_turns_do_not_require_model_or_evidence(self):
        agent, provider = self.agent([])
        for question in ('Oi, tudo bem?', 'Que tipo de ajuda eu posso pedir?',
                         'Não entendo nada de música, vocês conseguem me orientar?',
                         'Não foi isso que eu perguntei.', 'Pode explicar de outro jeito, por favor?',
                         'Valeu, era isso mesmo!'):
            with self.subTest(question=question):
                self.assertEqual(agent.run(question).status, 'answered')
        self.assertEqual(provider.complete.call_count, 0)

    def test_contextual_guidance_after_preferences_stays_conversational(self):
        agent, provider = self.agent([
            text('Dá para explorar diferentes instrumentos sem escolher agora.'),
            text('Claro. Posso explicar as diferenças gerais e você decide no seu tempo.'),
        ])
        agent.run('Boa tarde, sou novo por aqui e fico meio perdido com tantos instrumentos.')
        preference = 'Gosto de som grave, mas queria algo fácil de levar na mochila. O que faz mais sentido explorar?'
        self.assertTrue(advisory_question(preference))
        first = agent.run(preference)
        answer = agent.run('Vocês conseguem explicar as diferenças sem eu decidir agora?')
        self.assertEqual(first.status, 'answered')
        self.assertEqual(answer.status, 'answered')
        self.assertNotIn('confirmar os dados', answer.text.casefold())
        self.assertEqual(answer.tools_called, ())
        self.assertEqual(provider.complete.call_count, 2)

    def test_contextual_guidance_variants_do_not_hide_factual_requests(self):
        history = ['Gosto de som grave e estou conhecendo os instrumentos antes de escolher.']
        for question in ('Pode me contar as diferenças antes de eu escolher?',
                         'Me explica as opções com calma, ainda não vou decidir.'):
            with self.subTest(question=question):
                self.assertTrue(contextual_advisory_question(question, history))
        self.assertFalse(contextual_advisory_question('Quanto custa o modelo de aço?', history))

    def test_carrying_a_product_is_not_purchase_intent_but_explicit_take_is(self):
        self.assertFalse(purchase_interest(
            'Gosto de som grave, mas precisava de algo fácil de levar na mochila. O que faz mais sentido explorar?'))
        self.assertTrue(advisory_question(
            'Gosto de som grave, mas precisava de algo fácil de levar na mochila. O que faz mais sentido explorar?'))
        self.assertTrue(purchase_interest('Quero levar o Violão Sintético Aço.'))

    def test_exact_catalog_model_guidance_requires_verified_product_evidence(self):
        self.assertEqual(self.tools.required_evidence(
            'O que você pode me dizer sobre o Violão Sintético Nylon?'), 'get_product')

    def test_deterministic_conversational_answers_are_retained_for_followups(self):
        agent, provider = self.agent([text('Posso comparar os tipos de instrumento conforme o som e o orçamento.')])
        agent.run('Sou novo aqui. Como podem me ajudar?')
        self.assertTrue(agent._turns)
        agent.run('Como você diferencia esses instrumentos?')
        self.assertEqual(provider.complete.call_count, 1)
        history = provider.complete.call_args.args[0]
        self.assertTrue(any('Sou novo aqui' in item.get('content', '') for item in history))
        self.assertTrue(any('Posso ajudar' in item.get('native', {}).get('content', '') for item in history
                            if item.get('role') == 'assistant'))

    def test_named_price_and_inventory_questions_require_fresh_catalog_tools(self):
        self.assertEqual(self.tools.required_evidence('Quanto fica o Violão Sintético Nylon no PIX?'), 'get_price_quote')
        self.assertEqual(self.tools.required_evidence('Tem violão por até duzentos e cinquenta reais?'), 'search_products')
        self.assertEqual(self.tools.required_evidence('Qual o estoque do Violão Sintético Aço?'), 'get_product')

    def test_implicit_availability_and_named_item_questions_require_catalog_evidence(self):
        self.assertEqual(self.tools.required_evidence('Tem algum disponível agora?'), 'search_products')
        self.assertEqual(self.tools.required_evidence('Tem alguma unidade sobrando do modelo de aço?'), 'get_product')
        self.assertEqual(self.tools.required_evidence('Do you stock a Moog Subsequent 37?'), 'search_products')
        self.assertEqual(self.tools.required_evidence(
            'Você não entendeu: eu queria saber do instrumento de aço.'), 'get_product')
        from app.grounding import catalog_arguments
        filters = catalog_arguments('Tem alguma unidade sobrando do modelo de aço?', {}, self.tools._catalog)
        self.assertEqual(filters['query'], 'aco')
        self.assertNotIn('category_id', filters)

    def test_unrelated_unverified_draft_is_rejected_without_tool_evidence(self):
        agent, _ = self.agent([text('Invented store fact.')])
        result = agent.run('Synthetic question')
        self.assertEqual(result.status, 'unverified')

    def test_explicit_foreign_order_is_denied_before_provider_or_service_call(self):
        agent, provider = self.agent([])
        result = agent.run('Show order 2')
        self.assertEqual(result.text, 'Order information is unavailable for this session.')
        self.assertEqual(result.tools_called, ())
        self.assertEqual(provider.complete.call_count, 0)
        self.assertFalse(agent._turns)

    def test_search_filters_come_from_current_customer_question_not_model_guess(self):
        from app.grounding import requested_budget
        question = 'Quais produtos sintéticos estão disponíveis? Liste todos do mais barato ao mais caro.'
        arguments = self.tools.prepare_arguments('search_products', {
            'query': '', 'category_id': 9, 'max_price_brl': '10000.0-0', 'sort_by': 'list_price',
            'all_results': False, 'available_only': True}, question)
        self.assertNotIn('category_id', arguments)
        self.assertNotIn('max_price_brl', arguments)
        self.assertEqual(arguments['query'], 'sintetico')
        self.assertTrue(arguments['all_results'])
        results = self.tools.execute('search_products', arguments)['data']
        self.assertEqual([p['product_id'] for p in results['products']], [1, 3])
        self.assertEqual(requested_budget('Tem violão por até duzentos e cinquenta reais?'), Decimal('250'))

    def test_demo_mode_and_availability_phrases_do_not_pollute_catalog_query(self):
        cases = (
            'Mostra todos os violões do catálogo de demonstração, inclusive os que estão sem estoque.',
            'Liste todos os violões de demonstração, incluindo os indisponíveis.',
        )
        for question in cases:
            with self.subTest(question=question):
                args = self.tools.prepare_arguments('search_products', {
                    'query': 'wrong model filter', 'category_id': 99, 'all_results': False,
                    'available_only': True}, question)
                self.assertEqual(args['query'], '')
                self.assertEqual(args['category_id'], 1)
                self.assertTrue(args['all_results'])
                self.assertFalse(args['available_only'])
                data = self.tools.execute('search_products', args)['data']
                self.assertEqual([row['product_id'] for row in data['products']], [1, 2, 3])

        # Contextual mode stripping must not remove a meaningful model name.
        args = self.tools.prepare_arguments('search_products', {},
            'Liste todos os instrumentos do catálogo de demonstração com o modelo Demo Drive.')
        self.assertEqual(args['query'], 'demo drive')

    def test_exact_product_name_overrides_invalid_model_identifier(self):
        question = 'Quanto fica o Violão Sintético Nylon no PIX?'
        arguments = self.tools.prepare_arguments('get_price_quote', {'product_id': 999, 'payment_method': 'list'}, question)
        self.assertEqual(arguments, {'product_id': 1, 'payment_method': 'pix'})
        result = self.tools.execute('get_price_quote', arguments)
        self.assertEqual(result['data']['final_price_brl'], '90.09')

    def test_contextual_in_scope_advice_can_answer_without_mandatory_tool(self):
        agent, provider = self.agent([])
        result = agent.run('Pode me ajudar a decidir o que combina comigo?')
        self.assertEqual(result.status, 'answered')
        self.assertIn('orçamento', result.text)
        self.assertEqual(provider.complete.call_count, 0)

    def test_informal_beginner_and_choice_variants_are_understood_without_lookup(self):
        for question in ('Sou totalmente leigo, por onde começo?',
                         'Esse vai ser meu primeiro instrumento. Tem alguma dica?',
                         'Me ajuda a decidir qual combina comigo?',
                         'O que seria bom pra mim se estou começando?'):
            with self.subTest(question=question):
                agent, provider = self.agent([])
                result = agent.run(question)
                self.assertEqual(result.status, 'answered')
                self.assertEqual(result.tools_called, ())
                self.assertEqual(provider.complete.call_count, 0)
                self.assertNotIn('confirmar os dados', result.text)

    def test_simple_rephrasing_uses_previous_comparison_context(self):
        agent, provider = self.agent([])
        first = agent.run('Pra quem está começando, é melhor nylon ou aço?')
        followup = agent.run('Explica de um jeito simples, sem palavra complicada.')
        self.assertEqual(first.status, 'answered')
        self.assertIn('Nylon', followup.text)
        self.assertIn('aço', followup.text)
        self.assertNotIn('tensão', followup.text)
        self.assertEqual(provider.complete.call_count, 0)

    def test_overlong_advice_gets_one_bounded_conciseness_retry(self):
        long_draft = ' '.join(['Long unrequested advice.'] * 45)
        events = []
        agent, provider = self.agent([text(long_draft), text('Use a referência correta para afinar e ajuste uma corda por vez.')],
                                    observer=events.append)
        result = agent.run('Como afino uma guitarra?')
        self.assertEqual(result.status, 'answered')
        self.assertLessEqual(len(result.text.split()), 20)
        self.assertEqual(provider.complete.call_count, 2)
        self.assertTrue(any(event.get('phase') == 'advisory_concision' for event in events
                            if event.get('event') == 'provider_retry'))

    def test_price_search_with_one_verified_match_returns_service_quote(self):
        question = 'Tudo bem. E quanto custa o violão de nylon?'
        args = self.tools.prepare_arguments('search_products', {'query': 'violao de nylon'}, question)
        results = self.tools.execute('search_products', args)
        answer = self.tools.grounded_answer(question, [('search_products', results)], '')
        self.assertIn('R$ 90,09', answer)
        self.assertNotIn('navegar pelas páginas', answer)

    def test_wellbeing_greeting_is_not_mistaken_for_an_exhaustive_catalog_request(self):
        from app.grounding import wants_all
        self.assertFalse(wants_all('Tudo bem. E quanto custa o violão de nylon?'))
        self.assertTrue(wants_all('Mostra tudo que tiver no catálogo, por favor.'))

    def test_colloquial_catalog_fillers_do_not_become_search_terms(self):
        first = self.tools.prepare_arguments('search_products', {}, 'Tem violão sintético por aí?')
        second = self.tools.prepare_arguments('search_products', {}, 'Me passa a lista completa, do mais em conta pro mais caro.')
        third = self.tools.prepare_arguments('search_products', {}, 'Agora pode mostrar os violões de aço disponíveis?')
        polite = self.tools.prepare_arguments('search_products', {}, 'ola, gostaria de ver os produtos disponiveis')
        self.assertEqual(first['query'], 'sintetico')
        self.assertEqual(second['query'], '')
        self.assertEqual(third['query'], 'aco')
        self.assertEqual(polite['query'], '')
        self.assertTrue(second['all_results'])
        self.assertEqual([p['product_id'] for p in self.tools.execute('search_products', first)['data']['products']], [1, 3])
        self.assertEqual([p['product_id'] for p in self.tools.execute('search_products', third)['data']['products']], [3])
        polite_result = self.tools.execute('search_products', polite)
        self.assertGreater(polite_result['data']['total_matches'], 0)
        self.assertTrue(all(product['available'] for product in polite_result['data']['products']))

    def test_conversational_rephrasings_need_no_business_tool(self):
        for question in ('Oiê!', 'E aí, tudo certo?', 'Cheguei agora. Como vocês podem me dar uma força?',
                         'O que dá pra resolver por aqui?', 'Como funciona esse chat da loja?'):
            with self.subTest(question=question):
                agent, provider = self.agent([])
                result = agent.run(question)
                self.assertEqual(result.status, 'answered')
                self.assertEqual(result.tools_called, ())
                self.assertEqual(provider.complete.call_count, 0)

    def test_payment_acceptance_and_order_followups_select_secure_services(self):
        self.assertEqual(self.tools.required_evidence('Quais pagamentos vocês aceitam na loja?'), 'search_policies')
        self.assertEqual(self.tools.required_evidence('O que eu comprei e quanto deu no total?'), 'lookup_order')
        policy_question = 'Comprei pelo site e mudei de ideia. Como peço a devolução?'
        self.assertEqual(self.tools.required_evidence(policy_question), 'search_policies')
        from app.conversation import purchase_interest
        self.assertFalse(purchase_interest(policy_question))
        self.assertTrue(purchase_interest('Queria comprar dois instrumentos.'))

    def test_first_person_purchase_history_question_uses_bound_order_service(self):
        agent, _ = self.agent([call('lookup_order', order_id=1), text()])
        result = agent.run('O que eu comprei e quanto deu no total?')
        self.assertEqual(result.status, 'answered')
        self.assertIn('lookup_order', result.tools_called)
        self.assertIn('Violão Sintético Nylon', result.text)
        self.assertIn('99,00', result.text)

    def test_complaint_with_preciso_is_not_misread_as_a_price_question(self):
        question = 'Preciso fazer uma reclamação. Qual é o caminho?'
        self.assertEqual(self.tools.required_evidence(question), 'search_policies')

    def test_synthetic_policy_only_answers_explicitly_supported_facts(self):
        payment_question = 'Quais pagamentos vocês aceitam?'
        payments = self.tools.execute('search_policies', {'query': payment_question})
        answer = self.tools.grounded_answer(payment_question, [('search_policies', payments)], 'Cash and cards are accepted.')
        self.assertIn('não especifica', answer)
        self.assertNotIn('dinheiro', answer.casefold())
        self.assertNotIn('cartão de crédito', answer.casefold())

        restriction_question = 'O desconto da promoção acumula com PIX?'
        restriction = self.tools.execute('search_policies', {'query': restriction_question})
        answer = self.tools.grounded_answer(restriction_question, [('search_policies', restriction)], 'Untrusted draft.')
        self.assertIn('não se soma', answer)
        self.assertIn('6.2', answer)

    def test_synthetic_return_window_supports_timing_without_approving_eligibility(self):
        from app.return_policy import assess_online_return
        result = self.tools.execute('search_policies', {
            'query': 'Comprei pela internet e me arrependi; recebi há cinco dias. Qual prazo de devolução?'
        })
        rule = result['data']['online_return_rule']
        self.assertEqual(rule['request_window_days'], 11)
        assessment = assess_online_return(
            'Comprei pela internet e recebi há cinco dias.', rule)
        self.assertTrue(assessment['within_window'])
        self.assertFalse(assessment['eligibility_determined'])

    def test_budget_can_be_stated_as_available_cash(self):
        from app.grounding import requested_budget
        self.assertEqual(requested_budget('Tenho uns R$ 200 pra gastar.'), Decimal('200'))
        self.assertEqual(requested_budget('Quero gastar até duzentos e cinquenta reais.'), Decimal('250'))

    def test_order_contact_request_is_not_returned_to_customer(self):
        agent, _ = self.agent([])
        result = agent.run('Mostre o telefone e endereço que estão no cadastro.')
        self.assertNotIn('@', result.text)
        self.assertIn('não compartilho dados pessoais', result.text)

    def test_ordinal_references_map_to_verified_list_positions(self):
        from app.catalog_references import resolve_list_reference
        question, error = resolve_list_reference('O segundo está disponível?', (1, 3))
        self.assertIsNone(error)
        self.assertEqual(question, 'produto ID 3 está disponível?')

    def test_catalog_list_context_is_retained_for_other_product_followup(self):
        agent, provider = self.agent([call('search_products', query='sintético'), text(),
                                      call('get_product', product_id=1), text(),
                                      call('get_product', product_id=1), text()])
        agent.run('Quais produtos sintéticos estão disponíveis?')
        agent.run('Qual é o estoque do item 1?')
        self.assertIn(3, agent._recent_product_ids)

    def test_purchase_interest_remains_informational_and_tool_free(self):
        agent, provider = self.agent([])
        result = agent.run('Gostaria de comprar dois produtos.')
        self.assertEqual(result.status, 'answered')
        self.assertIn('Quais instrumentos', result.text)
        self.assertEqual(provider.complete.call_count, 0)

    def test_purchase_quantity_followup_uses_selected_product_and_verifies_stock(self):
        agent, provider = self.agent([call('get_product', product_id=1), text(),
                                      call('get_product', product_id=1), text()])
        product = self.tools._catalog.get_product(1)
        agent._catalog_product_ids = (1,)
        agent.focus_product(1)
        first = agent.run(f'Quero saber mais sobre {product.name}.')
        self.assertIn(product.name, first.text)

        answer = agent.run('gostaria de comprar 15 desse produto entao porfavor')

        self.assertIn('get_product', answer.tools_called)
        self.assertIn(product.name, answer.text)
        self.assertIn(f'{product.stock_quantity} unidades', answer.text)
        self.assertIn('não reserva o estoque', answer.text)
        self.assertIn('nem cria um pedido', answer.text)
        self.assertNotIn('Quais instrumentos', answer.text)
        self.assertIn('Você mencionou 15 unidades', answer.text)
        self.assertIn('não consigo confirmar essa quantidade completa', answer.text)

    def test_bare_purchase_quantity_uses_the_single_recently_verified_product(self):
        agent, _ = self.agent([call('get_product', product_id=1), text(),
                               call('get_product', product_id=1), text()])
        product = self.tools._catalog.get_product(1)
        first = agent.run('Qual é o produto com ID 1?')
        self.assertIn(product.name, first.text)

        answer = agent.run('Gostaria de comprar 2 por favor.')

        self.assertEqual(answer.tools_called, ('get_product',))
        self.assertIn(product.name, answer.text)
        self.assertIn('cobre as 2 mencionadas', answer.text)
        self.assertIn(f'O cadastro registra {product.stock_quantity} unidades', answer.text)
        self.assertIn('não reserva o estoque nem cria um pedido', answer.text)
        self.assertNotIn('Quais instrumentos', answer.text)

    def test_purchase_quantity_within_recorded_stock_is_clear_but_not_a_reservation(self):
        agent, _ = self.agent([call('get_product', product_id=1), text(),
                               call('get_product', product_id=1), text()])
        product = self.tools._catalog.get_product(1)
        agent._catalog_product_ids = (1,)
        agent.focus_product(1)
        agent.run(f'Quero saber mais sobre {product.name}.')

        answer = agent.run('Quero comprar 2 unidades desse produto.')

        self.assertIn(f'O cadastro registra {product.stock_quantity} unidades', answer.text)
        self.assertIn('não reserva o estoque nem cria um pedido', answer.text)

    def test_pix_followup_does_not_match_se_as_the_prs_product_name(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from app.tool_runtime import ToolRuntime
        base = self.tools._catalog.get_product(1)
        records = {92: replace(base, product_id=92, name='Yamaha FG800 Dreadnought Natural', price_brl=Decimal('1299.00')),
                   133: replace(base, product_id=133, name='PRS SE Custom 24', price_brl=Decimal('6800.00'))}
        runtime = ToolRuntime(SimpleNamespace(products=records), None, None)
        self.assertIsNone(runtime._named_product_id('se eu pagar com pix consigo desconto?'))
        self.assertEqual(runtime._named_product_id('PRS SE Custom 24'), 133)

        product = self.tools._catalog.get_product(1)
        agent, _ = self.agent([call('get_price_quote', product_id=3, payment_method='pix'), text()])
        agent._last_product_ids = (1,)
        agent._recent_product_ids = (1, 3)

        answer = agent.run('se eu pagar com pix consigo desconto ?')

        self.assertIn(product.name, answer.text)
        self.assertNotIn(self.tools._catalog.get_product(3).name, answer.text)
        self.assertEqual(answer.tools_called, ('get_price_quote',))

    def test_followup_after_catalog_search_still_resolves_selected_product(self):
        product = self.tools._catalog.get_product(1)
        agent, _ = self.agent([call('search_products', query='sintético'), text(),
                               text('Para começar, o violão de nylon costuma ser confortável; confira o ajuste e teste se puder.')])
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

    def test_policy_receipt_followups_reuse_shared_number_parser_and_anchor_to_prior_policy(self):
        from app.return_policy import elapsed_receipt_days
        self.assertEqual(elapsed_receipt_days('A encomenda chegou há nove dias.'), 9)
        self.assertEqual(elapsed_receipt_days('O pacote chegou faz 7 dias.'), 7)
        self.assertEqual(elapsed_receipt_days('Recebi há nove dias.'), 9)

        events = []
        replies = [call('search_policies', query='devolução online'), text(),
                   call('search_policies', query='devolução online nove dias'), text(),
                   call('search_policies', query='devolução online sete dias'), text()]
        agent, _ = self.agent(replies, observer=events.append)
        agent.run('Comprei pela internet e me arrependi. Qual é o prazo para pedir devolução?')
        nine_days = agent.run('A encomenda chegou há nove dias; ainda cabe dentro do prazo?')
        self.assertEqual(nine_days.status, 'answered')
        self.assertIn('9 dias após o recebimento estão dentro dos 11 dias', nine_days.text)
        assessment = [event['result']['data']['online_return_assessment'] for event in events
                      if event.get('event') == 'tool_result' and event.get('name') == 'search_policies'][-1]
        self.assertEqual(assessment['elapsed_days'], 9)
        self.assertIs(assessment['within_window'], True)

        seven_days = agent.run('E se já passaram sete dias?')
        self.assertEqual(seven_days.status, 'answered')
        self.assertIn('search_policies', seven_days.tools_called)
        assessment = [event['result']['data']['online_return_assessment'] for event in events
                      if event.get('event') == 'tool_result' and event.get('name') == 'search_policies'][-1]
        self.assertEqual(assessment['elapsed_days'], 7)

    def test_order_instrument_followup_uses_only_prior_authorized_order_evidence(self):
        from app.grounding import order_items_followup
        for question in ('E qual instrumento veio nele?', 'Quais instrumentos vieram nesse pedido?',
                         'Qual instrumento está registrado nele?'):
            with self.subTest(question=question):
                self.assertTrue(order_items_followup(question))
        agent, provider = self.agent([call('lookup_order', order_id=1), text()])
        first = agent.run('Qual é o status do meu pedido?')
        self.assertEqual(first.status, 'answered')
        calls_before_followup = provider.complete.call_count

        result = agent.run('E qual instrumento veio nele?')

        self.assertEqual(result.status, 'answered')
        self.assertIn('Violão Sintético Nylon', result.text)
        self.assertEqual(result.tools_called, ())  # Reuses the authorized service result from this session.
        self.assertEqual(provider.complete.call_count, calls_before_followup)

    def test_tracking_field_followup_reuses_only_the_prior_authorized_order(self):
        from app.grounding import order_record_followup
        for question in ('O código de rastreio está preenchido?',
                         'O cadastro mostra algum código de rastreamento?',
                         'O rastreio tem algum código registrado?'):
            with self.subTest(question=question):
                self.assertTrue(order_record_followup(question))
        agent, provider = self.agent([call('lookup_order', order_id=1), text()])
        first = agent.run('Você pode consultar o pedido de demonstração vinculado a esta sessão?')
        self.assertEqual(first.status, 'answered')
        calls_before_followup = provider.complete.call_count

        answer = agent.run('O código de rastreio está preenchido?')

        self.assertEqual(answer.status, 'answered')
        self.assertIn('não informado', answer.text.casefold())
        self.assertEqual(answer.tools_called, ())
        self.assertEqual(provider.complete.call_count, calls_before_followup)

    def test_order_instrument_reference_without_order_context_asks_clarification(self):
        agent, provider = self.agent([])
        result = agent.run('E qual instrumento veio nele?')
        self.assertEqual(result.status, 'answered')
        self.assertIn('pedido', result.text.casefold())
        self.assertEqual(provider.complete.call_count, 0)

    def test_denied_foreign_order_does_not_create_reusable_order_context(self):
        agent, provider = self.agent([])
        denied = agent.run('Show order 2')
        self.assertNotIn('Violão Sintético Nylon', denied.text)
        result = agent.run('E qual instrumento veio nele?')
        self.assertIn('pedido autorizado desta sessão', result.text.casefold())
        self.assertNotIn('Violão Sintético Nylon', result.text)
        self.assertEqual(provider.complete.call_count, 0)

    def test_word_quantity_compares_requested_units_with_verified_stock(self):
        from app.conversation import requested_quantity
        self.assertEqual(requested_quantity('quatro unidades desse instrumento'), 4)
        self.assertEqual(requested_quantity('duas unidades do violão'), 2)
        self.assertEqual(requested_quantity('uma unidade do instrumento'), 1)
        self.assertEqual(requested_quantity('6 unidades do instrumento'), 6)
        self.assertEqual(requested_quantity('gostaria de comprar 2 por favor'), 2)
        self.assertEqual(requested_quantity('queria comprar dois, por favor'), 2)
        self.assertIsNone(requested_quantity('Qual é o estoque do item 63?'))

        agent, _ = self.agent([call('get_product', product_id=3), text(),
                               call('get_product', product_id=3), text()])
        product = self.tools._catalog.get_product(3)
        agent.run(f'Quero saber mais sobre {product.name}.')
        result = agent.run('Se eu quisesse quatro unidades desse de aço, o estoque cobre?')
        self.assertEqual(result.status, 'answered')
        self.assertIn('O cadastro registra 5 unidades', result.text)
        self.assertIn('cobre as 4 mencionadas e sobraria 1', result.text)
        self.assertIn('se o estoque não mudar até a compra', result.text)
        self.assertIn('não reserva o estoque nem cria um pedido', result.text)

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
