"""Original-resource checks: no restricted text or personal records are copied."""

import os
import re
import unittest
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from app.orders import DemoSessionConfig, OrderService
from app.policies import HEADINGS, PolicyRetriever, normalize
from app.repository import Repository, SCHEMAS
from app.tool_runtime import ToolRuntime


DATA = Path(os.environ.get("EMPORIO_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
POLICY = DATA / "políticas_da_loja.pdf"


@unittest.skipUnless(POLICY.is_file(), "Authorized policy PDF is not installed")
class OriginalPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retriever = PolicyRetriever(POLICY)

    def test_all_profile_sections_and_cross_page_references(self):
        self.assertEqual(set(self.retriever.sections), set(HEADINGS) | {"cover"})
        for number, pages in [("4.1", (4,)), ("5.2", (4, 5)), ("7.2", (6, 7)), ("9", (7, 8))]:
            with self.subTest(number=number):
                self.assertEqual(self.retriever.sections[number].pages, pages)
                self.assertTrue(self.retriever.sections[number].text)

    def test_portuguese_retrieval_benchmark(self):
        # Sixteen explicit topic-coverage checks, not a general semantic accuracy claim.
        cases = [
            ("Quero devolver uma compra online", {"4.1", "4.4"}),
            ("Como solicitar reembolso?", {"4.1"}),
            ("Posso trocar a cor do instrumento?", {"4.3"}),
            ("Quero trocar um produto com defeito", {"4.2", "8.1"}),
            ("Como acionar a assistencia tecnica?", {"8.1", "8.2"}),
            ("Qual a garantia do fabricante?", {"8.2", "8.3"}),
            ("Posso acumular PIX com uma oferta?", {"3", "6.2"}),
            ("Quais formas de pagamento aceitam?", {"3", "3.1"}),
            ("Quero parcelar no cartao de credito", {"3.1"}),
            ("Quais as regras do frete?", {"5.1", "5.2"}),
            ("Como funciona o rastreio?", {"5.3"}),
            ("Qual o prazo de postagem?", {"5.2"}),
            ("Ate que horas voces atendem?", {"2"}),
            ("Abrem no sabado?", {"2"}),
            ("Estou insatisfeito e quero fazer uma queixa", {"7.3"}),
            ("Preciso registrar uma reclamacao", {"7.3"}),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                result = self.retriever.search(question)
                self.assertNotEqual(result.status, "insufficient_evidence")
                self.assertTrue(expected <= {s.number for s in result.sections})

    def test_store_location_retrieves_company_source_without_embedding_private_value(self):
        for question in ('Qual é o endereço da loja?', 'Onde fica a loja?', 'Como chegar à loja?'):
            with self.subTest(question=question):
                result = self.retriever.search(question)
                section = next((item for item in result.sections if item.number == '1.2'), None)
                self.assertIsNotNone(section)
                self.assertEqual(section.pages, (2,))
                self.assertRegex(section.text, r'(?i)\bRua\b.*\bMS\b.*\b\d{5}-\d{3}\b')
        repository = Repository(DATA)
        tools = ToolRuntime(repository, self.retriever, OrderService(repository))
        evidence = tools.execute('search_policies', {'query': 'Qual é o endereço da loja?'})
        answer = tools.grounded_answer('Qual é o endereço da loja?', [('search_policies', evidence)],
                                       'Untrusted extra phone/email details.')
        section = next(item for item in evidence['data']['sections'] if item['section'] == '1.2')
        address = re.search(r'(?i)\bendereço\s+(.+?)(?=\s+(?:telefone\b|whatsapp\b|e-mail\b|email\b))', section['text']).group(1).strip(' \t\r\n,;.')
        self.assertTrue(normalize(address) in normalize(answer))
        self.assertNotIn('@', answer)
        self.assertNotIn('telefone', normalize(answer))

    def test_actual_ambiguities_and_consistent_tracking_format(self):
        codes = {i.code for i in self.retriever.issues}
        self.assertTrue({"conflicting_contacts", "conflicting_email_spelling", "installment_minimum_conflict",
                         "installment_exception_ambiguous", "shipping_threshold_gap", "return_exception_scope",
                         "exchange_warranty_scope"} <= codes)
        self.assertNotIn("tracking_format_conflict", codes)
        self.assertEqual(self.retriever.search("PIX pode acumular com promocao?").status, "evidence_found")

    def test_unsupported_and_individual_queries_stay_insufficient(self):
        for question in ("Qual a capital da Franca?", "Posso pagar com bitcoin?", "Quanto custa o frete para meu CEP?",
                         "Qual a garantia especifica do Yamaha C40?", "Ja foi aprovado meu reembolso?"):
            with self.subTest(question=question):
                self.assertEqual(self.retriever.search(question).status, "insufficient_evidence")


@unittest.skipUnless(all((DATA / f"{name}.csv").is_file() for name in SCHEMAS),
                     "Authorized original CSVs are not installed")
class OriginalOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Repository(DATA)

    def test_every_order_is_owner_only_with_uniform_denials(self):
        for order in self.repo._orders.values():
            with self.subTest(order_id=order.order_id):
                owner = OrderService(self.repo, DemoSessionConfig(True, order.customer_id))
                self.assertEqual(owner.lookup_order(order.order_id).status, "available")
                another_id = next(cid for cid in self.repo._customers if cid != order.customer_id)
                stranger = OrderService(self.repo, DemoSessionConfig(True, another_id))
                self.assertEqual(stranger.lookup_order(order.order_id), stranger.lookup_order(999999))

    def test_historical_totals_and_missing_fields(self):
        order = self.repo._orders[3]
        service = OrderService(self.repo, DemoSessionConfig(True, order.customer_id))
        self.assertEqual(service.lookup_order(3).order.total_brl, Decimal("3450.00"))
        for order in self.repo._orders.values():
            result = OrderService(self.repo, DemoSessionConfig(True, order.customer_id)).lookup_order(order.order_id).order
            self.assertEqual(result.total_brl, order.total_brl)
            self.assertEqual(result.tracking_code, order.tracking_code)
            self.assertEqual(result.estimated_delivery, order.estimated_delivery)
            self.assertIsNone(result.actual_delivery)

    def test_cancelled_and_private_fields_are_preserved_or_excluded(self):
        for order in self.repo._orders.values():
            result = OrderService(self.repo, DemoSessionConfig(True, order.customer_id)).lookup_order(order.order_id)
            fields = asdict(result.order)
            self.assertTrue({"customer_id", "email", "phone", "address", "notes", "payment_method"}.isdisjoint(fields))
            self.assertEqual(result.order.status, order.status)
            self.assertIn("no action was taken", result.message)
