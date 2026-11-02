"""Mode isolation and UI/service integration; mocked inference is not a live run."""

import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from app.providers import ConfigurationError, ProviderReply, ToolCall
from app.repository import SCHEMAS
from app.web_session import ChatSession
from tests.helpers import fixture_rows, mock_shop_scope, write_fixture
from tests.policy_helpers import synthetic_pages, write_pdf


class LocalWebTests(unittest.TestCase):
    def setUp(self):
        mock_shop_scope(self)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        write_fixture(self.path, fixture_rows())
        write_pdf(self.path / 'policy.pdf', synthetic_pages())
        self.env = {'EMPORIO_DATA_MODE': 'local', 'EMPORIO_DATA_DIR': str(self.path),
                    'EMPORIO_POLICY_PATH': str(self.path / 'policy.pdf')}

    def session(self, extra=None, replies=()):
        provider = Mock(external=False)
        provider.complete.side_effect = list(replies)
        factory = Mock(return_value=provider)
        session = ChatSession(environment=self.env | (extra or {}), provider_factory=factory)
        self.addCleanup(session.close)
        return session, provider, factory

    def test_local_uses_all_records_and_full_policy_and_only_loopback_ollama(self):
        session, _, factory = self.session({'LLM_PROVIDER': 'gemini', 'GEMINI_API_KEY': 'not-a-real-key'})
        self.assertEqual(session.mode, 'LOCAL')
        self.assertFalse(session._tools.is_synthetic)
        self.assertEqual(len(session._tools._catalog.repository.products), len(fixture_rows()['products']))
        self.assertIn('4.1', session._tools._policies.sections)
        self.assertEqual(factory.call_args.args[0].provider, 'ollama')
        self.assertEqual(factory.call_args.args[0].base_url, 'http://127.0.0.1:11434')

    def test_local_identity_and_order_are_startup_bound_and_reset_preserves_them(self):
        session, _, _ = self.session({'EMPORIO_ENABLE_DEMO_IDENTITY': '1', 'EMPORIO_DEMO_CUSTOMER_ID': '1'})
        self.assertEqual(session.order_details().status, 'available')
        self.assertEqual(session.order_details().order.total_brl, Decimal('99.00'))
        self.env['EMPORIO_DEMO_CUSTOMER_ID'] = '2'
        session.reset()
        self.assertEqual(session.order_details().status, 'available')
        with self.assertRaises(AttributeError):
            session.mode = 'DEMO'

    def test_anonymous_and_foreign_selected_order_have_uniform_denials(self):
        rows = fixture_rows()
        rows['customers'].append(dict(rows['customers'][0], customer_id='2', email='second@example.invalid'))
        write_fixture(self.path, rows)
        anonymous, _, _ = self.session()
        missing, _, _ = self.session({'EMPORIO_ENABLE_DEMO_IDENTITY': '1', 'EMPORIO_DEMO_CUSTOMER_ID': '1', 'EMPORIO_ORDER_ID': '999'})
        foreign, _, _ = self.session({'EMPORIO_ENABLE_DEMO_IDENTITY': '1', 'EMPORIO_DEMO_CUSTOMER_ID': '2'})
        self.assertEqual(anonymous.order_details(), missing.order_details())
        self.assertEqual(foreign.order_details(), missing.order_details())
        self.assertIsNone(anonymous.order_details().order)

    def test_missing_local_files_fail_without_falling_back_to_demo(self):
        for changes in ({'EMPORIO_DATA_DIR': str(self.path / 'missing')},
                        {'EMPORIO_POLICY_PATH': str(self.path / 'missing.pdf')}):
            with patch('app.data_session.SyntheticTools') as synthetic:
                with self.assertRaises(ValueError):
                    self.session(changes)
                synthetic.assert_not_called()

    def test_demo_is_independent_and_rejects_local_paths_identity_and_order_overrides(self):
        with patch('app.data_session.Repository', side_effect=AssertionError('No local repository in DEMO')):
            demo = ChatSession(environment={}, provider_factory=lambda c: Mock(external=False))
        self.addCleanup(demo.close)
        self.assertEqual(demo.mode, 'DEMO')
        self.assertEqual(len(demo._tools._catalog.repository.products), 3)
        for key, value in [('EMPORIO_DATA_DIR', str(self.path)), ('EMPORIO_POLICY_PATH', 'private.pdf'),
                           ('EMPORIO_DEMO_CUSTOMER_ID', '3'), ('EMPORIO_ENABLE_DEMO_IDENTITY', '1'),
                           ('EMPORIO_ORDER_ID', '4')]:
            with self.assertRaises(ValueError):
                ChatSession(environment={key: value}, provider_factory=Mock())

    def test_unknown_mode_remote_endpoint_and_external_factory_fail_closed(self):
        for env in ({'EMPORIO_DATA_MODE': 'cloud'}, {'OLLAMA_BASE_URL': 'https://example.invalid'}):
            factory = Mock()
            with self.assertRaises(ValueError):
                ChatSession(environment=env, provider_factory=factory)
            factory.assert_not_called()
        external = Mock(external=True)
        with self.assertRaises(ConfigurationError):
            ChatSession(environment=self.env, provider_factory=lambda c: external)
        external.complete.assert_not_called()

    def test_complete_catalog_can_include_unavailable_then_return_to_available_only(self):
        session, _, _ = self.session()
        tools = session._tools
        question = 'Liste o catálogo completo, incluindo produtos indisponíveis e inativos.'
        args = tools.prepare_arguments('search_products', {'query': 'catálogo completo incluindo produtos indisponíveis e inativos'}, question)
        data = tools.execute('search_products', args)['data']
        self.assertEqual(len(data['products']), len(fixture_rows()['products']))
        self.assertFalse(data['truncated'])
        text = tools.grounded_answer(question, [('search_products', {'status': 'ok', 'data': data})], '')
        self.assertIn('Indisponível', text)
        self.assertNotIn('demonstração', text)
        args = tools.prepare_arguments('search_products', {'available_only': False}, 'Liste todos os produtos disponíveis.')
        self.assertTrue(args['available_only'])
        self.assertTrue(all(p['available'] for p in tools.execute('search_products', args)['data']['products']))

    def test_stock_and_category_use_product_evidence_instead_of_generated_numbers(self):
        session, _, _ = self.session(replies=[
            ProviderReply('', (ToolCall('get_product', {'product_id': 2}),), {}),
            ProviderReply('Stock is 999 units in the wrong category.', (), {})])
        result = session.ask('What is the category and recorded stock for product 1?')
        self.assertIn('Category: Violões', result.text)
        stock = session._tools._catalog.get_product(1).stock_quantity
        self.assertIn(f'Recorded stock: {stock} units', result.text)
        self.assertNotIn('999', result.text)

    def test_local_references_never_claim_synthetic_and_order_dto_has_no_contacts(self):
        session, _, _ = self.session({'EMPORIO_ENABLE_DEMO_IDENTITY': '1', 'EMPORIO_DEMO_CUSTOMER_ID': '1'}, [
            ProviderReply('', (ToolCall('search_policies', {'query': 'garantia'}),), {}),
            ProviderReply('Confirm the conditions with customer service.', (), {})])
        answer = session.ask('Qual é a garantia?')
        self.assertTrue(answer.references)
        self.assertTrue(all(ref.startswith('Store policy') for ref in answer.references))
        from dataclasses import asdict
        encoded = json.dumps(asdict(session.order_details()), default=str)
        for forbidden in ('test@example.invalid', 'TEST-ONLY', 'Synthetic Person', 'notes'):
            self.assertNotIn(forbidden, encoded)

    @unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Optional Streamlit absent')
    def test_same_page_uses_local_prompts_order_view_and_preserves_chat(self):
        from streamlit.testing.v1 import AppTest
        session, _, _ = self.session({'EMPORIO_ENABLE_DEMO_IDENTITY': '1', 'EMPORIO_DEMO_CUSTOMER_ID': '1'}, [
            ProviderReply('', (ToolCall('search_products', {'query': ''}),), {}), ProviderReply('Catalog', (), {})])
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app/streamlit_app.py'))
        with patch('app.web_session.ChatSession', return_value=session):
            app.run()
            self.assertTrue(any('LOCAL' in c.value for c in app.caption))
            next(b for b in app.button if b.label == 'Ver produtos').click().run()
            self.assertNotIn('sintético', app.session_state.messages[0]['text'])
            previous = list(app.session_state.messages)
            next(b for b in app.button if b.label == 'Meu pedido').click().run()
            self.assertTrue(any('registro da loja' in c.value for c in app.caption))
            self.assertTrue(any('99,00' in m.value for m in app.markdown))
            app.button(key='back_to_chat').click().run()
            self.assertEqual(previous, app.session_state.messages)
            self.assertFalse(app.exception)


ORIGINAL_DATA = Path(__file__).resolve().parents[1] / 'data'


@unittest.skipUnless(all((ORIGINAL_DATA / f'{name}.csv').is_file() for name in SCHEMAS) and
                     (ORIGINAL_DATA / 'políticas_da_loja.pdf').is_file(), 'Authorized original resources absent')
class OriginalLocalWebTests(unittest.TestCase):
    def test_all_sixty_five_fit_the_existing_tool_budget_and_all_pdf_sections_load(self):
        from app.policies import HEADINGS
        session = ChatSession(environment={'EMPORIO_DATA_MODE': 'local', 'EMPORIO_DATA_DIR': str(ORIGINAL_DATA)},
                              provider_factory=lambda c: Mock(external=False))
        self.addCleanup(session.close)
        self.assertEqual(len(session._tools._catalog.repository.products), 65)
        self.assertEqual(set(session._tools._policies.sections), set(HEADINGS) | {'cover'})
        data = session._tools.execute('search_products', {'all_results': True, 'available_only': False,
                                                        'sort_by': 'effective_price'})['data']
        self.assertEqual((data['total_matches'], data['returned_count'], data['truncated']), (65, 65, False))
        self.assertEqual(sum(p['available'] for p in data['products']), 61)
        prices = [Decimal(p['effective_price_brl']) for p in data['products']]
        self.assertEqual(prices, sorted(prices))
        self.assertEqual(session.order_details().status, 'unavailable')
