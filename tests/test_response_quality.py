"""Presentation regressions over real synthetic services, not live LLM transcripts."""

import unittest
from unittest.mock import Mock

from app.agent import Agent
from app.grounding import render_catalog, render_quote, render_order
from app.providers import ProviderReply, ToolCall
from app.return_policy import render_online_return
from app.synthetic import SyntheticTools


class ResponseQualityTests(unittest.TestCase):
    def setUp(self):
        self.tools = SyntheticTools()
        self.addCleanup(self.tools.close)

    def test_bilingual_catalog_keeps_complete_sorted_prices_and_list_spacing(self):
        data = self.tools.execute('search_products', {'all_results': True, 'sort_by': 'effective_price'})['data']
        for english in (False, True):
            text = render_catalog(data, self.tools._catalog.repository.categories, english=english, synthetic=True)
            self.assertIn('demonstration' if english else 'demonstração', text)
            self.assertIn('complete' if english else 'completa', text)
            prices = ['90.09', '250.00'] if english else ['90,09', '250,00']
            self.assertLess(text.index(prices[0]), text.index(prices[1]))
            self.assertEqual(sum(line[:1].isdigit() for line in text.splitlines()), data['total_matches'])
            self.assertIn('\n\n1.', text)
            self.assertIn('\n\nPrices' if english else '\n\nOs preços', text)
            for term in ('snapshot', 'list_price_brl', 'tool_call', 'data retrieval', 'arquivos fornecidos'):
                self.assertNotIn(term, text)
            local_text = render_catalog(data, self.tools._catalog.repository.categories, english=english)
            self.assertNotIn('demonstration' if english else 'demonstração', local_text)

    def test_partial_and_quality_warnings_are_not_lost_in_friendlier_copy(self):
        data = self.tools.execute('search_products', {'all_results': True})['data']
        data['truncated'] = True
        data['total_matches'] = 9
        data['products'][0]['warnings'] = ['attribute_conflict']
        data['products'][0]['issues'] = ['Brand conflict / Marca: nome A; descrição B.']
        for english in (False, True):
            text = render_catalog(data, {}, english=english)
            self.assertIn('2 of 9' if english else '2 de 9', text)
            self.assertIn('partial' if english else 'parcial', text)
            self.assertIn('Brand conflict / Marca: nome A; descrição B.', text)

    def test_pix_promotion_restriction_unavailability_and_prices_remain_truthful(self):
        for product_id, available in [(1, True), (2, False)]:
            data = self.tools.execute('get_price_quote', {'product_id': product_id, 'payment_method': 'pix'})['data']
            for english in (False, True):
                text = render_quote(data, 'Test instrument', english=english, synthetic=True)
                self.assertNotIn('snapshot', text)
                self.assertIn('demonstration' if english else 'demonstração', text)
                self.assertIn(data['final_price_brl'] if english else data['final_price_brl'].replace('.', ','), text)
                if product_id == 1:
                    self.assertIn('no additional PIX discount' if english else 'não se soma', text)
                if not available:
                    self.assertIn('unavailable' if english else 'indisponível', text)

    def test_order_total_missing_dates_and_denial_survive_presentation(self):
        data = self.tools.execute('lookup_order', {'order_id': 1})['data']
        for english in (False, True):
            text = render_order(data, english=english, synthetic=True)
            self.assertIn('99.00' if english else '99,00', text)
            self.assertIn('not recorded' if english else 'não informado', text)
            self.assertIn('original' if english else 'original', text)
            self.assertNotIn('snapshot', text)
            self.assertNotIn('tracking_code', text)
            denied = self.tools.execute('lookup_order', {'order_id': 2})['data']
            self.assertNotIn('2', render_order(denied, english=english))

    def test_five_day_policy_answer_leads_with_timing_without_approving_return(self):
        question = 'Comprei online e me arrependi depois de 5 dias do recebimento. Posso devolver?'
        data = {'online_return_rule': {'request_window_days': 7, 'section': '4.1', 'pages': [4],
                                     'conditions_statement': 'O produto deve estar sem sinais de uso.',
                                     'refund_statement': 'O reembolso será realizado na mesma forma de pagamento original em até 3 dias úteis.'}}
        text = render_online_return(question, data)
        self.assertTrue(text.startswith('Sim'))
        for term in ('5 dias', '7 dias corridos', 'não significa que ela já foi aprovada',
                     'sem sinais de uso', '3 dias úteis', 'seção 4.1', 'página 4'):
            self.assertIn(term, text)
        self.assertNotIn('elegibilidade', text)
        self.assertNotIn('após a validação', text)

    def test_current_language_and_trusted_data_mode_reach_each_business_request(self):
        def scope(language):
            return ProviderReply('', (ToolCall('check_shop_scope', {'decision': 'shop', 'language': language}),), {})
        provider = Mock(external=False)
        provider.complete.side_effect = [scope('pt'),
            ProviderReply('', (ToolCall('get_price_quote', {'product_id': 1, 'payment_method': 'pix'}),), {}),
            ProviderReply('Price', (), {}), scope('en'),
            ProviderReply('', (ToolCall('search_policies', {'query': 'warranty'}),), {}),
            ProviderReply('The demonstration policy needs clarification. Section 8.1, page 24.', (), {})]
        agent = Agent(provider, self.tools)
        agent.run('Qual é o preço do produto 1 no PIX?')
        result = agent.run('What is your warranty policy?')
        calls = provider.complete.call_args_list
        self.assertIn('Current reply language: Brazilian Portuguese', calls[2].args[2])
        self.assertIn('Current reply language: English', calls[5].args[2])
        self.assertIn('Trusted data mode: synthetic demonstration data', calls[5].args[2])
        self.assertEqual(calls[5].args[0][0]['content'], 'Qual é o preço do produto 1 no PIX?')
        self.assertTrue(calls[5].args[0][-3]['content'].endswith('Please respond in English.'))
        stored_questions = [m['content'] for turn in agent._turns for m in turn if m['role'] == 'user']
        self.assertEqual(stored_questions, ['Qual é o preço do produto 1 no PIX?', 'What is your warranty policy?'])
        self.assertEqual(result.tools_called, ('search_policies',))
        self.assertIn('8.1', result.text)

    def test_prior_catalog_does_not_authorize_invented_warranty_terms(self):
        from tests.helpers import mock_shop_scope
        mock_shop_scope(self)
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply('', (ToolCall('search_products', {'all_results': True}),), {}),
            ProviderReply('Catalog', (), {}),
            ProviderReply('No warranties. Everything is sold as is. Section 3.1, page 5.', (), {}),
            ProviderReply('', (ToolCall('search_policies', {'query': 'warranty'}),), {}),
            ProviderReply('No warranties. Everything is sold as is.', (), {})]
        agent = Agent(provider, self.tools)
        agent.run('Please list all products.')
        result = agent.run('What is your warranty policy?')
        self.assertEqual(result.tools_called, ('search_policies',))
        self.assertIn("doesn't specify", result.text)
        self.assertIn('8.1 (p. 24)', result.text)
        self.assertNotIn('as is', result.text)
        self.assertNotIn('No warranties', str(agent._turns))
