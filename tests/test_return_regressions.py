"""Policy clock/answer regressions. Contradictory fake prose is intentional."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app.agent import Agent
from tests.helpers import mock_shop_scope
from app.orders import OrderService
from app.policies import PolicyRetriever
from app.providers import ProviderReply, ToolCall
from app.repository import Repository
from app.tool_runtime import ToolRuntime
from tests.helpers import fixture_rows, write_fixture
from tests.policy_helpers import synthetic_pages, write_pdf


QUESTION = "Comprei um violão pela internet e me arrependi. Posso devolver depois de 5 dias do recebimento? Como funciona o reembolso?"
WRONG = "A política de devolução não permite devolução após 5 dias do recebimento. A seção 4.1 permite solicitar em até 7 dias."
DATA = Path(os.environ.get("EMPORIO_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


def rule_text(window=7, refund=3):
    # Synthetic values/conditions. Variable windows ensure no hardcoded seven-day answer.
    return (f"O cliente pode solicitar a devolução em até {window} dias corridos após o recebimento do produto. "
            "• O produto deve estar na embalagem original e sem sinais de uso. "
            f"• O reembolso será realizado na mesma forma de pagamento original em até {refund} dias úteis. "
            "• O frete de devolução é por conta da loja em caso de arrependimento.")


class ReturnRegressionTests(unittest.TestCase):
    def setUp(self):
        mock_shop_scope(self)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        write_fixture(self.path, fixture_rows())
        self.repo = Repository(self.path)

    def runtime(self, text=None):
        pages = synthetic_pages()
        for page in pages:
            for i, line in enumerate(page):
                if line.startswith("Devolucao online:"):
                    page[i] = rule_text() if text is None else text
        write_pdf(self.path / "policy.pdf", pages)
        return ToolRuntime(self.repo, PolicyRetriever(self.path / "policy.pdf"), OrderService(self.repo))

    def run_question(self, question=QUESTION, text=None, prose=WRONG):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("search_policies", {"query": "devolução online e reembolso"}),), {}), ProviderReply(prose, (), {})]
        events = []
        agent = Agent(provider, self.runtime(text), observer=events.append)
        return agent.run(question), events, agent

    def test_five_days_is_within_seven_even_when_model_contradicts_it(self):
        result, events, agent = self.run_question()
        self.assertEqual(result.status, "answered")
        self.assertTrue(result.text.startswith("Sim"))
        self.assertIn("5 dias", result.text)
        self.assertIn("7 dias", result.text)
        self.assertNotIn("não permite", result.text)
        self.assertIn("condições", result.text)
        data = next(e["result"]["data"] for e in events if e["event"] == "tool_result")
        self.assertEqual(data["online_return_assessment"]["within_window"], True)
        self.assertFalse(data["online_return_assessment"]["eligibility_determined"])
        self.assertNotIn(WRONG, str(agent._turns))

    def test_window_and_refund_are_extracted_not_hardcoded(self):
        result, events, _ = self.run_question(text=rule_text(window=11, refund=3))
        self.assertIn("11 dias", result.text)
        self.assertNotIn("7 dias", result.text)
        self.assertIn("3 dias úteis", result.text)
        self.assertNotIn("10 dias", result.text)
        self.assertNotIn("após a validação", result.text)

    def test_inclusive_boundaries_and_outside_window(self):
        for elapsed, within in [(0, True), (7, True), (8, False)]:
            with self.subTest(elapsed=elapsed):
                question = QUESTION.replace("5 dias", f"{elapsed} dias")
                result, events, _ = self.run_question(question)
                assessment = next(e["result"]["data"]["online_return_assessment"] for e in events if e["event"] == "tool_result")
                self.assertEqual(assessment["within_window"], within)
                self.assertEqual(result.text.startswith("Sim"), within)
                if not within:
                    self.assertIn("ultrapassam", result.text)

    def test_purchase_clock_business_days_and_ambiguous_elapsed_days_are_not_assumed(self):
        questions = [QUESTION.replace("do recebimento", "da compra"), QUESTION.replace("5 dias", "5 dias úteis"),
                     QUESTION + " Também recebi há 8 dias.", QUESTION + " Ainda não recebi o produto."]
        for question in questions:
            with self.subTest(question=question):
                result, events, _ = self.run_question(question)
                assessment = next(e["result"]["data"]["online_return_assessment"] for e in events if e["event"] == "tool_result")
                self.assertIsNone(assessment["within_window"])
                self.assertFalse(result.text.startswith("Sim"))

    def test_missing_or_conflicting_rule_fails_closed_instead_of_repeating_model_claim(self):
        for text in ("Synthetic online returns require staff confirmation.", rule_text() + " " + rule_text(window=9)):
            with self.subTest(text=text):
                result, _, _ = self.run_question(text=text, prose="Yes, the limit is definitely 7 days")
                self.assertIn("não consigo confirmar", result.text.casefold())
                self.assertNotIn("definitely", result.text)
                self.assertFalse(result.text.startswith("Sim"))

    def test_rewritten_tool_query_cannot_drop_customer_timing_and_channel(self):
        _, events, _ = self.run_question()
        event = next(e for e in events if e["event"] == "tool_result")
        self.assertNotIn("5", event["requested_arguments"]["query"])
        self.assertEqual(event["effective_arguments"]["query"], QUESTION)
        self.assertEqual({s["section"] for s in event["result"]["data"]["sections"]}, {"4.1", "4.4"})
        self.assertEqual(event["result"]["data"]["online_return_assessment"]["elapsed_days"], 5)

    def test_new_timed_policy_question_requires_fresh_policy_evidence(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("get_product", {"product_id": 1}),), {}), ProviderReply("A catalog fact", (), {}),
                                         ProviderReply(WRONG, (), {}),
                                         ProviderReply("", (ToolCall("search_policies", {"query": "reembolso"}),), {}), ProviderReply(WRONG, (), {})]
        agent = Agent(provider, self.runtime())
        agent.run("Show product ID 1")
        result = agent.run(QUESTION)
        self.assertTrue(result.text.startswith("Sim"))
        self.assertEqual(result.tools_called, ("search_policies",))

    def test_spelled_five_days_and_unknown_refund_start(self):
        result, _, _ = self.run_question(QUESTION.replace("5 dias", "cinco dias"))
        self.assertTrue(result.text.startswith("Sim"))
        self.assertIn("5 dias", result.text)
        self.assertIn("mesma forma de pagamento original", result.text)
        self.assertNotIn("após a validação", result.text)
        separate_clocks, _, _ = self.run_question(QUESTION + " O reembolso leva 3 dias úteis?")
        self.assertTrue(separate_clocks.text.startswith("Sim"))


@unittest.skipUnless((DATA / "políticas_da_loja.pdf").is_file(), "Authorized original PDF absent")
class OriginalReturnRegressionTests(unittest.TestCase):
    def setUp(self):
        ReturnRegressionTests.setUp(self)
    def test_actual_pdf_five_day_window_and_refund(self):
        tools = ToolRuntime(self.repo, PolicyRetriever(DATA / "políticas_da_loja.pdf"), OrderService(self.repo))
        result = tools.execute("search_policies", {"query": QUESTION})["data"]
        self.assertEqual(result["online_return_rule"]["request_window_days"], 7)
        self.assertEqual(result["online_return_rule"]["refund_business_days"], 10)
        self.assertTrue(result["online_return_assessment"]["within_window"])
        self.assertEqual(result["online_return_rule"]["pages"], [4])
