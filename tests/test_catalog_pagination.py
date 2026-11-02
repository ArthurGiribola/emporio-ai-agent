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
        for index in range(17):
            rows, count, page, pages = catalog_page(view, page=index)
            self.assertEqual((count, page, pages), (65, index, 17))
            self.assertEqual(len(rows), 4 if index < 16 else 1)
            self.assertTrue(all(e.name and e.category and e.price_brl is not None for e in rows))
            collected.extend(e.position for e in rows)
        self.assertEqual(collected, list(range(1, 66)))
        rows, _, _, _ = catalog_page(view, category_id=2)
        self.assertEqual([e.position for e in rows], [1, 4, 7, 10])
        self.assertEqual(catalog_page(view, category_id=999)[0], ())
        self.assertEqual(catalog_page(view, page=999)[2], 16)
        self.assertEqual(catalog_page(view, page=-2)[2], 0)
        rows, count, page, pages = catalog_page(view, search='INSTRUMENT 63', page=99)
        self.assertEqual(([e.position for e in rows], count, page, pages), ([63], 1, 0, 1))
        self.assertEqual(catalog_page(view, category_id=2, search='instrument 63')[1], 0)
        accented = replace(view, entries=(replace(view.entries[0], name='Violão Nylon'),))
        self.assertEqual(catalog_page(accented, search='violao')[1], 1)

    def test_projection_reads_validated_services_not_generated_values(self):
        with SyntheticTools() as tools:
            data = tools.execute('search_products', {'all_results': True})['data']
            data['products'][0]['name'] = 'Invented model name'
            data['products'][0]['list_price_brl'] = '0.01'
            view = build_catalog_view(tools._catalog, data, synthetic=True)
            self.assertEqual(view.entries[0].name, tools._catalog.get_product(1).name)
            self.assertEqual(view.entries[0].price_brl, tools._catalog.get_price_quote(1).final_price_brl)
            self.assertEqual(view.entries[0].price_brl, Decimal('90.09'))
            self.assertEqual(view.entries[0].promotion_percent, Decimal('10'))
            self.assertEqual(view.entries[0].base_price_brl, Decimal('100.10'))
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
        selection_patch = patch.object(self.session, 'select_product')
        self.selection = selection_patch.start()
        self.addCleanup(selection_patch.stop)
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
        self.assertFalse(any(s.key == 'catalog_pick' for s in self.app.selectbox))
        self.assertEqual(self.app.button(key='catalog_product_1001').label,
                         'Item 1\n\n**Synthetic instrument 1**\n\nR$ 1,00 · Disponível')
        self.assertIn('R$ 1,00', self.app.button(key='catalog_product_1001').label)
        self.assertEqual(len([b for b in self.app.button if b.key and b.key.startswith('catalog_product_')]), 4)
        self.assertTrue(self.app.button(key='catalog_previous').disabled)
        for _ in range(15):
            self.app.button(key='catalog_next').click().run()
        self.app.button(key='catalog_product_1063').click().run()
        self.assertIn('Synthetic instrument 63', self.markup())
        self.assertIn('Estoque registrado: 63 unidades', self.markup())
        self.app.button(key='catalog_detail_back').click().run()
        self.assertEqual(self.app.session_state.catalog_page, 15)
        self.app.button(key='catalog_next').click().run()
        self.assertTrue(self.app.button(key='catalog_next').disabled)
        self.app.selectbox(key='catalog_category').set_value(2).run()
        self.assertEqual(self.app.session_state.catalog_page, 0)
        self.assertIsNone(self.app.session_state.catalog_pick)
        self.assertIn('Item 10', self.app.button(key='catalog_product_1010').label)
        self.app.text_input(key='catalog_search').set_value('instrument 13').run()
        self.assertEqual(len([b for b in self.app.button if b.key and b.key.startswith('catalog_product_')]), 1)
        self.app.button(key='catalog_product_1013').click().run()
        self.app.button(key='catalog_detail_back').click().run()
        self.assertEqual(self.app.text_input(key='catalog_search').value, 'instrument 13')
        self.assertEqual(self.app.selectbox(key='catalog_category').value, 2)
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

    def test_row_hierarchy_and_header_only_mode_in_both_themes(self):
        self.open_catalog()
        for _ in range(4):
            self.app.button(key='catalog_next').click().run()
        for light in (False, True):
            if light:
                self.app.button(key='theme_toggle').click().run()
            for position in range(17, 21):
                row = self.app.button(key=f'catalog_product_{1000+position}')
                self.assertEqual(row.label.split('\n\n'),
                    [f'Item {position}', f'**Synthetic instrument {position}**', f'R$ {position},00 · Disponível'])
                self.assertEqual(row.proto.icon_position, 1)  # Native right-side chevron.
            markup = self.markup()
            self.assertEqual(markup.count('class="mode-indicator">DEMO'), 1)
            self.assertFalse(any('Ollama' in c.value or 'Identidade fixa' in c.value for c in self.app.caption))
            self.assertFalse(self.app.exception)
        self.app.button(key='catalog_product_1017').click().run()
        self.assertFalse(any('Somente leitura' in c.value for c in self.app.caption))

    def test_empty_result_remains_conversational_and_does_not_show_stale_catalog(self):
        self.open_catalog()
        self.app.button(key='catalog_back').click().run()
        self.agent.return_value = AgentResult('answered', 'No matching products.', catalog=CatalogView((), 0, False, True))
        self.app.chat_input[0].set_value('Find an unknown instrument').run()
        self.assertIsNone(self.app.session_state.catalog_view)
        self.assertFalse(self.app.selectbox)
        self.assertIn('No matching products.', self.app.chat_message[-1].markdown[0].value)
        self.assertFalse(self.app.exception)

    def test_full_visible_transcript_survives_all_internal_navigation(self):
        self.agent.return_value = AgentResult('answered', 'Resposta verificada.')
        for n in range(10):
            self.app.chat_input[0].set_value(f'Pergunta da loja {n}').run()
        original = list(self.app.session_state.messages)
        self.assertEqual(len(original), 20)
        self.agent.return_value = AgentResult('answered', '', catalog=self.view)
        self.open_catalog()
        self.app.button(key='catalog_product_1001').click().run()
        self.app.button(key='catalog_detail_back').click().run()
        self.app.button(key='catalog_back').click().run()
        next(b for b in self.app.button if b.label == 'Meu pedido').click().run()
        self.app.button(key='back_to_chat').click().run()
        self.assertEqual(self.app.session_state.messages[:20], original)
        self.assertEqual(len(self.app.chat_message), 23)  # Greeting + 11 complete turns.
        self.assertIn('Pergunta da loja 0', self.app.chat_message[1].text[0].value)
        self.assertFalse(self.app.exception)

    def test_ask_action_uses_record_identity_and_retains_browser_context(self):
        self.open_catalog()
        self.app.selectbox(key='catalog_category').set_value(2).run()
        self.app.text_input(key='catalog_search').set_value('instrument 13').run()
        self.app.button(key='catalog_product_1013').click().run()
        self.agent.return_value = AgentResult('answered', 'Verified answer about this instrument.')
        self.app.button(key='catalog_ask').click().run()
        self.assertEqual(self.agent.call_args.args[0], 'Quero saber mais sobre o item 13: Synthetic instrument 13.')
        self.assertEqual(self.app.session_state.view, 'chat')
        self.assertIn('Verified answer', self.app.chat_message[-1].markdown[0].value)
        next(b for b in self.app.button if b.label == 'Abrir catálogo').click().run()
        self.assertIn('Synthetic instrument 13', self.markup())
        self.app.button(key='catalog_detail_back').click().run()
        self.assertEqual(self.app.text_input(key='catalog_search').value, 'instrument 13')
        self.assertEqual(self.app.selectbox(key='catalog_category').value, 2)
        self.app.text_input(key='catalog_search').set_value('unmatched').run()
        self.assertTrue(self.app.button(key='catalog_previous').disabled)
        self.assertTrue(self.app.button(key='catalog_next').disabled)
        self.assertFalse(any(b.key and b.key.startswith('catalog_product_') for b in self.app.button))
        self.assertFalse(self.app.exception)

    def test_missing_values_zero_stock_escaping_and_partial_results(self):
        bad = replace(self.view.entries[0], name='<script>bad</script>', price_brl=None,
                      stock_quantity=None, category='', issues=())
        self.agent.return_value = AgentResult('answered', '', catalog=CatalogView((bad,), 65, True, True))
        self.open_catalog()
        self.assertIn('Preço não confirmado', self.app.button(key='catalog_product_1001').label)
        self.assertTrue(any('parcial' in c.value for c in self.app.caption))
        self.app.button(key='catalog_product_1001').click().run()
        self.assertIn('&lt;script&gt;', self.markup())
        self.assertNotIn('<script>', self.markup())
        self.assertIn('Estoque registrado: não informado', self.markup())
        self.assertNotIn('precisam de confirmação', self.markup())
        self.app.button(key='reset_chat').click().run()
        self.assertIsNone(self.app.session_state.catalog_view)
        self.assertTrue(self.app.chat_input)
        zero = replace(bad, name='Out of stock', stock_quantity=0, available=False)
        self.agent.return_value = AgentResult('answered', '', catalog=CatalogView((zero,), 1, False, True))
        self.open_catalog()
        self.app.button(key='catalog_product_1001').click().run()
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
        self.assertEqual([e.position for e in catalog_page(result.catalog, page=15)[0]], [61, 62, 63, 64])
        catalog_page(result.catalog, category_id=5, page=1)
        session._agent._turns.clear()  # The reference map must outlive bounded model context.
        for position in (62, 63):
            entry = result.catalog.entries[position-1]
            answer = session.ask(f'qual e o estoque do item {position}')
            self.assertIn(entry.name, answer.text)
            self.assertIn(f'{entry.stock_quantity} unidades', answer.text)
            self.assertNotIn('Wrong stock', answer.text)
        self.assertIn('Marca', '\n'.join(result.catalog.entries[61].issues))
