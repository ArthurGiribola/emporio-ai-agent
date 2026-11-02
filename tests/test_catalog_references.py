import unittest
from unittest.mock import Mock

from app.agent import Agent
from app.catalog_references import resolve_list_reference
from app.providers import ProviderReply, ToolCall
from app.synthetic import SyntheticTools
from tests.helpers import mock_shop_scope


class CatalogReferenceTests(unittest.TestCase):
    def test_large_verified_catalog_does_not_need_a_model_to_retype_the_rows(self):
        from dataclasses import replace
        from decimal import Decimal
        from unittest.mock import patch
        mock_shop_scope(self)
        with SyntheticTools() as tools:
            base = tools._catalog.get_product(1)
            products = {100+i: replace(base, product_id=100+i, name=f'Test instrument {i}',
                                     price_brl=Decimal(i+1)) for i in range(12)}
            provider = Mock(external=False)
            provider.complete.side_effect = [ProviderReply('', (ToolCall('search_products', {'all_results': True}),), {})]
            agent = Agent(provider, tools)
            with patch.object(tools._catalog.repository, 'products', products):
                result = agent.run('Liste todos os produtos disponíveis.')
            self.assertEqual(result.status, 'answered')
            self.assertEqual(len(agent._catalog_product_ids), 12)
            self.assertEqual(sum(line[:1].isdigit() for line in result.text.splitlines()), 12)
            self.assertEqual(provider.complete.call_count, 1)

    def test_positions_explicit_ids_and_ambiguous_references(self):
        for q in ('qual e o estoque do item 2', 'Qual é o preço do produto 2 no PIX?', 'What is the stock for product 2?'):
            result, error = resolve_list_reference(q, (81, 143))
            self.assertIsNone(error)
            self.assertIn('143', result)
        self.assertEqual(resolve_list_reference('produto ID 81 no PIX', (99,))[0], 'produto 81 no PIX')
        for q, ids in [('item 63', (81,)), ('item 1', ()), ('item 1 e produto 2', (81, 143))]:
            self.assertIsNotNone(resolve_list_reference(q, ids)[1])
        self.assertEqual(resolve_list_reference('pedido 2', (81, 143)), ('pedido 2', None))
        self.assertEqual(resolve_list_reference('item 1 do pedido 2', (81, 143)), ('item 1 do pedido 2', None))

    def test_list_followup_uses_ordered_product_ids_and_reset_clears_mapping(self):
        mock_shop_scope(self)
        with SyntheticTools() as tools:
            provider = Mock(external=False)
            provider.complete.side_effect = [
                ProviderReply('', (ToolCall('search_products', {'all_results': True, 'sort_by': 'effective_price'}),), {}),
                ProviderReply('Catalog', (), {}),
                ProviderReply('', (ToolCall('get_product', {'product_id': 2}),), {}),
                ProviderReply('Wrong stock: 999', (), {}),
                ProviderReply('', (ToolCall('search_products', {'all_results': True, 'max_price_brl': '150'}),), {}),
                ProviderReply('New catalog', (), {})]
            events = []
            agent = Agent(provider, tools, observer=events.append)
            agent.run('Liste todos os produtos disponíveis.')
            self.assertEqual(agent._catalog_product_ids, (1, 3))
            result = agent.run('qual e o estoque do item 2')
            self.assertEqual(result.status, 'answered')
            self.assertIn(tools._catalog.get_product(3).name, result.text)
            self.assertNotIn('999', result.text)
            event = [e for e in events if e['event'] == 'tool_result'][-1]
            self.assertEqual(event['effective_arguments']['product_id'], 3)
            self.assertEqual(agent._turns[-1][0]['content'], 'qual e o estoque do item 2')
            agent.run('Liste todos os produtos até R$150.')
            self.assertEqual(agent._catalog_product_ids, (1,))
            result = agent.run('Qual o estoque do item 2?')
            self.assertEqual(result.tools_called, ())
            self.assertIn('última lista', result.text)
            agent.reset()
            self.assertEqual(agent._catalog_product_ids, ())

    def test_exact_original_item_63_maps_to_named_battery(self):
        from pathlib import Path
        from app.web_session import ChatSession
        path = Path(__file__).resolve().parents[1] / 'data'
        if not (path / 'products.csv').is_file():
            self.skipTest('Original files absent')
        session = ChatSession(environment={'EMPORIO_DATA_MODE': 'local'}, provider_factory=lambda c: Mock(external=False))
        self.addCleanup(session.close)
        data = session._tools.execute('search_products', {'available_only': False, 'all_results': True, 'sort_by': 'effective_price'})['data']
        self.assertEqual(data['products'][62]['name'], 'Bateria Acústica Yamaha Kit 3 Studio')
        question, error = resolve_list_reference('qual e o estoque do item 63', tuple(p['product_id'] for p in data['products']))
        self.assertIsNone(error)
        args = session._tools.prepare_arguments('get_product', {'product_id': 63}, question)
        product = session._tools.execute('get_product', args)['data']
        self.assertEqual(product['name'], data['products'][62]['name'])

    def test_plain_text_is_not_reparsed_as_product_sections(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Optional Streamlit absent')
        import tempfile
        import sys
        from pathlib import Path
        source = "from app.streamlit_app import show_answer\nshow_answer({'text': 'Catálogo completo\\n\\n' + '\\n'.join(f'{i}. Instrumento {i} — R$ 10,00' for i in range(1,66)) + '\\n\\nSome source details need confirmation.\\nPrices include promotions.'})"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'page.py'
            path.write_text(source, encoding='utf-8')
            # AppTest replaces __main__; restore it before Windows spawn tests.
            original_main = sys.modules['__main__']
            try:
                app = AppTest.from_file(str(path)).run()
            finally:
                sys.modules['__main__'] = original_main
            self.assertFalse(app.expander)
            self.assertEqual(len(app.markdown), 1)
            self.assertIn('63. Instrumento 63', app.markdown[0].value)
            self.assertFalse(app.exception)
