"""Opt-in actual Ollama correctness regressions. Never send source files to Gemini."""

import os
import socket
import unittest
from pathlib import Path

from app.agent import Agent
from app.orders import OrderService
from app.policies import PolicyRetriever
from app.providers import ProviderConfig, create_provider
from app.repository import Repository, SCHEMAS
from app.tool_runtime import ToolRuntime


DATA = Path(os.environ.get("EMPORIO_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
READY = all((DATA / f"{name}.csv").is_file() for name in SCHEMAS) and (DATA / "políticas_da_loja.pdf").is_file()


@unittest.skipUnless(os.environ.get("EMPORIO_RUN_LIVE") == "1" and READY, "Requires opt-in live Ollama and authorized original resources")
class LiveCorrectnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            with socket.create_connection(("127.0.0.1", 11434), timeout=1):
                pass
        except OSError:
            raise unittest.SkipTest("Local Ollama server unavailable")
        cls.repo = Repository(DATA)
        cls.policies = PolicyRetriever(DATA / "políticas_da_loja.pdf")

    def make_agent(self, events):
        config = ProviderConfig(provider="ollama", model=os.environ.get("OLLAMA_MODEL", "qwen3:4b-instruct"),
                                timeout_seconds=120, max_output_tokens=2048)
        return Agent(create_provider(config), ToolRuntime(self.repo, self.policies, OrderService(self.repo)), observer=events.append)

    def test_real_multiturn_catalog_returns_all_twelve_correctly_sorted(self):
        events = []
        agent = self.make_agent(events)
        agent.run("Quais ukuleles estão disponíveis até R$ 1000?")
        events.clear()
        result = agent.run("Existem outros violões disponíveis por até R$ 1.000? Quero ver todos os modelos, do mais barato para o mais caro.")
        self.assertEqual(result.status, "answered", result.text)
        data = [e["result"]["data"] for e in events if e["event"] == "tool_result" and e["name"] == "search_products" and e["result"]["status"] == "ok"][-1]
        self.assertEqual([p["product_id"] for p in data["products"]], [83, 85, 89, 88, 81, 84, 87, 86, 107, 82, 91, 112])
        self.assertFalse(data["truncated"])
        self.assertEqual(data["returned_count"], data["total_matches"])
        self.assertTrue(all(p["category_id"] == 5 and p["available"] for p in data["products"]))
        self.assertNotIn("Kala", result.text)
        self.assertNotIn("list_price_brl", result.text)
        self.assertEqual(sum(line[:1].isdigit() for line in result.text.splitlines()), 12)

    def test_real_online_return_five_days_is_within_seven_with_conditions(self):
        events = []
        agent = self.make_agent(events)
        agent.run("Qual a diferença entre troca por defeito e devolução por arrependimento?")
        events.clear()
        result = agent.run("Comprei um violão pela internet e me arrependi. Posso devolver depois de 5 dias do recebimento? Como funciona o reembolso?")
        self.assertEqual(result.status, "answered", result.text)
        data = [e["result"]["data"] for e in events if e["event"] == "tool_result" and e["name"] == "search_policies" and e["result"]["status"] == "ok"][-1]
        self.assertEqual(data["online_return_rule"]["request_window_days"], 7)
        self.assertEqual(data["online_return_rule"]["refund_business_days"], 10)
        self.assertEqual(data["online_return_assessment"]["elapsed_days"], 5)
        self.assertTrue(data["online_return_assessment"]["within_window"])
        self.assertFalse(data["online_return_assessment"]["eligibility_determined"])
        self.assertTrue(result.text.startswith("Sim"))
        self.assertIn("5 dias", result.text)
        self.assertIn("7 dias", result.text)
        self.assertIn("10 dias úteis", result.text)
        self.assertIn("condições", result.text)
        self.assertNotIn("não permite", result.text)
        self.assertNotIn("após a validação", result.text)
