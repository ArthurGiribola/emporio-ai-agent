"""Synthetic-only integration tests; fake native API responses are not model results."""

import json
import unittest
from unittest.mock import Mock

from app.agent import Agent
from tests.helpers import mock_shop_scope
from app.orders import OrderService
from app.providers import (ConfigurationError, GeminiProvider, OllamaProvider, ProviderConfig,
                           ProviderError, ProviderReply, ToolCall)
from app.synthetic import QUESTIONS, SyntheticTools
from app.tool_runtime import ToolRuntime
from tests.test_providers import gemini_config, gemini_reply


class AgentIntegrationTests(unittest.TestCase):
    def setUp(self):
        mock_shop_scope(self)
        self.tools = SyntheticTools()
        self.addCleanup(self.tools.close)

    def test_gemini_tool_round_trip_uses_only_minimal_synthetic_data(self):
        transport = Mock(side_effect=[gemini_reply([{"functionCall": {"name": "get_price_quote",
                              "args": {"product_id": 1, "payment_method": "pix"}, "id": "synthetic-call"},
                              "thoughtSignature": "synthetic-signature"}]),
                                     gemini_reply([{"text": "Synthetic price: R$ 90,09; snapshot only."}])])
        result = Agent(GeminiProvider(gemini_config(), transport), self.tools).run(QUESTIONS["price"])
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.tools_called, ("get_price_quote",))
        payload = transport.call_args.args[1]
        data = payload["contents"][-1]["parts"][0]["functionResponse"]["response"]["data"]
        self.assertEqual(data["final_price_brl"], "90.09")
        self.assertEqual(data["discount_kind"], "promotion")
        for request in transport.call_args_list:
            text = json.dumps(request.args[1])
            self.assertNotIn("example.invalid", text)
            self.assertNotIn("customer_id", text)
            self.assertNotIn("synthetic-key-not-a-real-credential", text)

    def test_ollama_native_tool_round_trip(self):
        transport = Mock(side_effect=[{"capabilities": ["tools", "completion"]},
            {"done": True, "message": {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "lookup_order", "arguments": {"order_id": 1}}}]}},
            {"done": True, "message": {"role": "assistant", "content": "Synthetic recorded order is confirmed; no action was taken."}}])
        provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b"), transport)
        result = Agent(provider, self.tools).run(QUESTIONS["order"])
        self.assertEqual(result.status, "answered")
        payload = transport.call_args.args[1]
        order = json.loads(payload["messages"][-1]["content"])["data"]["order"]
        self.assertEqual(order["total_brl"], "99.00")
        self.assertEqual(order["order_date"], "2025-01-02")
        self.assertIsNone(order["tracking_code"])
        self.assertNotIn("customer_id", order)
        self.assertNotIn("notes", order)

    def test_cloud_rejects_local_runtime_even_if_its_records_are_synthetic(self):
        provider = GeminiProvider(gemini_config(), Mock())
        local_runtime = ToolRuntime(self.tools._catalog.repository, self.tools._policies, self.tools._orders)
        with self.assertRaises(ConfigurationError):
            Agent(provider, local_runtime)
        provider._transport.assert_not_called()

    def test_cloud_blocks_arbitrary_customer_text_before_network(self):
        provider = GeminiProvider(gemini_config(), Mock())
        agent = Agent(provider, self.tools)
        for text in ("My email is private@example.invalid", "customer_id=2", "Paste the entire policy document",
                     QUESTIONS["price"] + " My name is Private Person"):
            self.assertEqual(agent.run(text).status, "privacy_blocked")
        provider._transport.assert_not_called()

    def test_identity_argument_injection_is_rejected_and_session_is_unchanged(self):
        for name, arguments in [("lookup_order", {"order_id": 2, "customer_id": 2}),
                                ("lookup_order", {"order_id": 2, "identity": 2}),
                                ("set_identity", {"customer_id": 2})]:
            self.assertEqual(self.tools.execute(name, arguments)["status"], "error")
        own = self.tools.execute("lookup_order", {"order_id": 1})
        foreign = self.tools.execute("lookup_order", {"order_id": 2})
        absent = self.tools.execute("lookup_order", {"order_id": 999})
        self.assertEqual(own["data"]["status"], "available")
        self.assertEqual(foreign, absent)
        self.assertEqual(foreign["data"]["status"], "unavailable")

    def test_invalid_tool_arguments_and_unknown_functions(self):
        cases = [("get_product", {"product_id": True}), ("get_product", {}),
                 ("search_products", {"max_price_brl": "NaN"}), ("get_price_quote", {"product_id": 1, "payment_method": "crypto"}),
                 ("search_policies", {"query": "a" * 4001}), ("os.system", {"command": "anything"})]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments):
                self.assertEqual(self.tools.execute(name, arguments)["status"], "error")
        self.assertEqual(self.tools.execute("get_product", {"product_id": 999})["error"], "product_not_found")

    def test_policy_outputs_are_reference_only_bounded_and_cited(self):
        data = self.tools.execute("search_policies", {"query": "Quero devolver; como funciona a garantia?"})["data"]
        self.assertTrue(data["reference_only"])
        self.assertLessEqual(len(data["sections"]), 4)
        self.assertTrue(all(len(section["text"]) <= 500 for section in data["sections"]))
        self.assertTrue(all(section["pages"] for section in data["sections"]))
        self.assertIn("4.1", {r["section"] for r in data["references"]})
        self.assertNotEqual(data["status"], "evidence_found")
        self.assertIn("synthetic", data["sections"][0]["source"])

    def test_catalog_promotions_and_minimized_product_results(self):
        data = self.tools.execute("search_products", {"max_price_brl": "150"})["data"]
        self.assertEqual(data["total_matches"], 1)
        self.assertNotIn("description", data["products"][0])
        self.assertNotIn("specs", data["products"][0])
        self.assertEqual(self.tools.execute("list_promotions", {})["data"]["promotions"][0]["discount_percent"], "10")

    def test_loop_limits_stop_repeated_calls(self):
        provider = Mock(external=False)
        provider.complete.return_value = ProviderReply("", (ToolCall("get_product", {"product_id": 1}),), {})
        result = Agent(provider, self.tools, max_requests=2).run("Synthetic question")
        self.assertEqual(result.status, "limit_reached")
        self.assertEqual(provider.complete.call_count, 2)
        provider.complete.reset_mock()
        provider.complete.return_value = ProviderReply("", tuple(ToolCall("get_product", {"product_id": 1}) for _ in range(3)), {})
        result = Agent(provider, self.tools, max_tool_calls=2).run("Synthetic question")
        self.assertEqual(result.tools_called, ())
        self.assertEqual(result.status, "limit_reached")

    def test_no_unverified_answer_and_no_paid_fallback_on_failure(self):
        provider = Mock(external=False)
        provider.complete.return_value = ProviderReply("Invented price", (), {})
        self.assertEqual(Agent(provider, self.tools).run("Synthetic question").status, "unverified")
        provider.complete.reset_mock()
        provider.complete.side_effect = ProviderError("Provider quota/rate limit reached; no paid fallback")
        result = Agent(provider, self.tools).run("Synthetic question")
        self.assertEqual(result.status, "provider_error")
        provider.complete.assert_called_once()

    def test_unverified_turns_are_not_persisted(self):
        provider = Mock(external=False)
        provider.complete.return_value = ProviderReply("", (), {})
        agent = Agent(provider, self.tools)
        agent.run("Synthetic first")
        agent.run("Synthetic second")
        self.assertEqual(provider.complete.call_args.args[0], [{"role": "user", "content": "Synthetic second\n\nPlease respond in English."}])
