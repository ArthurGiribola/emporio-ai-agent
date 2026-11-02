"""Deterministic service/UI tests. These fixtures are not live LLM transcripts."""

from dataclasses import replace
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from app.agent import Agent, AgentResult
from app.catalog_view import CatalogEntry, CatalogView, build_catalog_view, catalog_page, product_issues
from app.providers import ProviderReply, ToolCall
from app.synthetic import SyntheticTools
from app.web_session import ChatSession
from app.services import PricingConflictError
from tests.helpers import mock_shop_scope


def synthetic_view():
    entries = tuple(CatalogEntry(i, 1000+i, f'Synthetic instrument {i}', 1+i % 3,
                                f'Category {1+i % 3}', Decimal(i), True, i) for i in range(1, 66))
    return CatalogView(entries, 65, False, True)


class CatalogPaginationTests(unittest.TestCase):
    def test_all_65_records_are_browsable_once_without_changing_positions(self):
        view = synthetic_view()
        collected = []
        for index in range(7):
            rows, count, page, pages = catalog_page(view, page=index)
            self.assertEqual((count, page, pages), (65, index, 7))
            self.assertEqual(len(rows), 10 if index < 6 else 5)
            self.assertTrue(all(e.name and e.category and e.price_brl is not None for e in rows))
            collected.extend(e.position for e in rows)
        self.assertEqual(collected, list(range(1, 66)))
        rows, _, _, _ = catalog_page(view, category_id=2)
        self.assertEqual([e.position for e in rows], [1, 4, 7, 10, 13, 16, 19, 22, 25, 28])
        self.assertEqual(catalog_page(view, category_id=999)[0], ())
        self.assertEqual(catalog_page(view, page=999)[2], 6)
        self.assertEqual(catalog_page(view, page=-2)[2], 0)

    def test_projection_reads_validated_services_not_generated_values(self):
        with SyntheticTools() as tools:
            data = tools.execute('search_products', {'all_results': True})['data']
            data['products'][0]['name'] = 'Invented model name'
            data['products'][0]['list_price_brl'] = '0.01'
            view = build_catalog_view(tools._catalog, data, synthetic=True)
            self.assertEqual(view.entries[0].name, tools._catalog.get_product(1).name)
            self.assertEqual(view.entries[0].price_brl, tools._catalog.get_price_quote(1).final_price_brl)
            self.assertEqual(view.entries[0].price_brl, Decimal('90.09'))
            self.assertEqual(tools._catalog.get_price_quote(1, payment_method='pix').final_price_brl, Decimal('90.09'))
            self.assertFalse(view.entries[0].issues)
            with patch.object(tools._catalog, 'get_price_quote', side_effect=PricingConflictError()):
                unavailable = build_catalog_view(tools._catalog, data)
                self.assertIsNone(unavailable.entries[0].price_brl)
                self.assertIn('promoções ativas concorrentes', unavailable.entries[0].issues[0])
            with patch.object(tools._catalog, 'get_product', side_effect=KeyError('missing')):
                with self.assertRaises(KeyError):
                    build_catalog_view(tools._catalog, data)

    def test_specific_issues_and_no_generic_warning_for_clean_product(self):
        with SyntheticTools() as tools:
            base = tools._catalog.get_product(1)
            self.assertEqual(product_issues(base), ())
            conflict = replace(base, name='Pearl Kit', description='Yamaha kit', specs={})
            issue = product_issues(conflict)[0]
            self.assertIn('Marca', issue)
            self.assertIn('pearl', issue.casefold())
            self.assertIn('yamaha', issue.casefold())
            self.assertIn('nome', issue)
            self.assertIn('descrição', issue)
            inactive = replace(base, status='inactive', stock_quantity=3)
            self.assertIn('3 unidades', product_issues(inactive)[0])


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Optional Streamlit absent')
class CatalogPageUITests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        original_main = sys.modules['__main__']
        self.addCleanup(lambda: sys.modules.__setitem__('__main__', original_main))
        self.session = ChatSession(environment={}, provider_factory=lambda c: Mock(external=False))
        self.addCleanup(self.session.close)
        self.view = synthetic_view()
        agent_patch = patch.object(self.session._agent, 'run', return_value=AgentResult('answered', 'untrusted prose', catalog=self.view))
        self.agent = agent_patch.start()
        self.addCleanup(agent_patch.stop)
        factory_patch = patch('app.web_session.ChatSession', return_value=self.session)
        self.factory = factory_patch.start()
        self.addCleanup(factory_patch.stop)
        self.app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py')).run()

    def open_catalog(self):
        next(b for b in self.app.button if b.label == 'Ver produtos').click().run()
        self.assertFalse(self.app.exception)

    def markup(self):
        return '\n'.join(element.proto.body for element in self.app.get('html'))

    def test_real_rows_pagination_category_selection_and_back(self):
        self.open_catalog()
        self.assertIn('1. Synthetic instrument 1', self.markup())
        self.assertIn('10. Synthetic instrument 10', self.markup())
        self.assertIn('Category 2', self.markup())
        self.assertIn('R$ 1,00', self.markup())
        self.assertEqual(self.markup().count('class="catalog-row"'), 10)
        self.assertTrue(self.app.button(key='catalog_previous').disabled)
        for _ in range(6):
            self.app.button(key='catalog_next').click().run()
        self.assertEqual(self.markup().count('class="catalog-row"'), 5)
        self.assertIn('63. Synthetic instrument 63', self.markup())
        self.assertTrue(self.app.button(key='catalog_next').disabled)
        self.app.selectbox(key='catalog_pick').set_value(63).run()
        self.assertIn('Synthetic instrument 63', self.markup())
        self.assertIn('Estoque registrado: 63 unidades', self.markup())
        self.app.selectbox(key='catalog_category').set_value(2).run()
        self.assertEqual(self.app.session_state.catalog_page, 0)
        self.assertIsNone(self.app.session_state.catalog_pick)
        self.assertIn('13. Synthetic instrument 13', self.markup())
        self.assertNotIn('2. Synthetic instrument 2<', self.markup())
        self.assertEqual(self.agent.call_count, 1, 'Filtering and pagination must not call the LLM')
        self.app.button(key='catalog_back').click().run()
        self.assertTrue(self.app.chat_input)
        self.assertEqual(len(self.app.chat_message), 3)
        self.agent.return_value = AgentResult('answered', 'A short normal answer.')
        self.app.chat_input[0].set_value('hello').run()
        self.assertEqual(self.app.session_state.view, 'chat')
        self.assertFalse(self.app.selectbox)
        self.assertIn('A short normal answer.', self.app.chat_message[-1].markdown[0].value)
        self.assertFalse(self.app.exception)

    def test_empty_result_remains_conversational_and_does_not_show_stale_catalog(self):
        self.open_catalog()
        self.app.button(key='catalog_back').click().run()
        self.agent.return_value = AgentResult('answered', 'No matching products.', catalog=CatalogView((), 0, False, True))
        self.app.chat_input[0].set_value('Find an unknown instrument').run()
        self.assertIsNone(self.app.session_state.catalog_view)
        self.assertFalse(self.app.selectbox)
        self.assertIn('No matching products.', self.app.chat_message[-1].markdown[0].value)
        self.assertFalse(self.app.exception)

    def test_missing_values_zero_stock_escaping_and_partial_results(self):
        bad = replace(self.view.entries[0], name='<script>bad</script>', price_brl=None,
                      stock_quantity=None, category='', issues=())
        self.agent.return_value = AgentResult('answered', '', catalog=CatalogView((bad,), 65, True, True))
        self.open_catalog()
        self.assertIn('Preço não confirmado', self.markup())
        self.assertIn('&lt;script&gt;', self.markup())
        self.assertNotIn('<script>', self.markup())
        self.assertTrue(any('parcial' in c.value for c in self.app.caption))
        self.app.selectbox(key='catalog_pick').set_value(1).run()
        self.assertIn('Estoque registrado: não informado', self.markup())
        self.assertNotIn('precisam de confirmação', self.markup())
        self.app.button(key='reset_chat').click().run()
        self.assertIsNone(self.app.session_state.catalog_view)
        self.assertTrue(self.app.chat_input)
        zero = replace(bad, name='Out of stock', stock_quantity=0, available=False)
        self.agent.return_value = AgentResult('answered', '', catalog=CatalogView((zero,), 1, False, True))
        self.open_catalog()
        self.app.selectbox(key='catalog_pick').set_value(1).run()
        self.assertIn('Estoque registrado: 0 unidades', self.markup())
        self.assertIn('Indisponível', self.markup())


DATA = Path(__file__).resolve().parents[1] / 'data'


@unittest.skipUnless((DATA / 'políticas_da_loja.pdf').is_file(), 'Original private data absent')
class OriginalCatalogPageTests(unittest.TestCase):
    def test_original_65_and_items_62_63_remain_correct_after_browsing_and_context_pruning(self):
        mock_shop_scope(self)
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply('', (ToolCall('search_products', {'all_results': True, 'available_only': False}),), {}),
            ProviderReply('', (ToolCall('get_product', {'product_id': 62}),), {}), ProviderReply('Wrong stock', (), {}),
            ProviderReply('', (ToolCall('get_product', {'product_id': 63}),), {}), ProviderReply('Wrong stock', (), {})]
        session = ChatSession(environment={'EMPORIO_DATA_MODE': 'local'}, provider_factory=lambda c: provider)
        self.addCleanup(session.close)
        result = session._agent.run('Liste o catálogo completo, incluindo produtos indisponíveis e inativos.')
        self.assertEqual(len(result.catalog.entries), 65)
        self.assertEqual([e.position for e in catalog_page(result.catalog, page=6)[0]], [61, 62, 63, 64, 65])
        catalog_page(result.catalog, category_id=5, page=1)
        session._agent._turns.clear()  # The reference map must outlive bounded model context.
        for position in (62, 63):
            entry = result.catalog.entries[position-1]
            answer = session.ask(f'qual e o estoque do item {position}')
            self.assertIn(entry.name, answer.text)
            self.assertIn(f'{entry.stock_quantity} unidades', answer.text)
            self.assertNotIn('Wrong stock', answer.text)
        self.assertIn('Marca', '\n'.join(result.catalog.entries[61].issues))
