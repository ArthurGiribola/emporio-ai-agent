"""Regressions for gaps observed during actual English evaluation."""

import unittest
from unittest.mock import Mock

from app.agent import Agent
from tests.helpers import mock_shop_scope
from app.providers import ProviderReply, ToolCall
from app.synthetic import SyntheticTools


class EnglishEvaluationTests(unittest.TestCase):
    def setUp(self):
        mock_shop_scope(self)
        self.tools = SyntheticTools()
        self.addCleanup(self.tools.close)

    def test_all_is_not_a_product_filter_and_customer_output_is_english(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("search_products", {"query": "all", "all_results": True, "max_price_brl": "10000", "category_id": 99}),), {}),
                                         ProviderReply("There are no products", (), {})]
        events = []
        result = Agent(provider, self.tools, observer=events.append).run("Please list all available products, sorted from the lowest to the highest price.")
        self.assertEqual(result.status, "answered")
        self.assertIn("2 available instruments", result.text)
        self.assertIn("complete list", result.text)
        self.assertNotIn("Não encontrei", result.text)
        self.assertNotIn("list_price_brl", result.text)
        event = next(e for e in events if e["event"] == "tool_result")
        self.assertEqual(event["effective_arguments"]["query"], "")
        self.assertNotIn("max_price_brl", event["effective_arguments"])
        self.assertNotIn("category_id", event["effective_arguments"])
        self.assertEqual(event["result"]["data"]["returned_count"], 2)

    def test_english_policy_topics_retrieve_existing_evidence(self):
        for query, expected in [("returns and refunds", "4.1"), ("warranty", "8.1"),
                                ("shipping", "5.2"), ("opening hours", "2"), ("complaints", "7.3")]:
            with self.subTest(query=query):
                result = self.tools.execute("search_policies", {"query": query})["data"]
                self.assertIn(expected, {s["section"] for s in result["references"]})

    def test_pix_quote_does_not_imply_pix_payment_is_forbidden(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("get_price_quote", {"product_id": 3, "payment_method": "list"}),), {}),
                                         ProviderReply("PIX cannot be used with the promotion; consult our live system", (), {})]
        events = []
        result = Agent(provider, self.tools, observer=events.append).run("What is the PIX price for product ID 1? Can I combine it with the promotion?")
        self.assertIn("90.09", result.text)
        self.assertIn("no additional PIX discount", result.text)
        self.assertNotIn("cannot be used", result.text)
        self.assertNotIn("live system", result.text)
        self.assertEqual(next(e["effective_arguments"] for e in events if e["event"] == "tool_result"), {"product_id": 1, "payment_method": "pix"})

    def test_order_followup_is_plain_language_and_new_order_is_checked_again(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("lookup_order", {"order_id": 1}),), {}),
                                         ProviderReply("tracking_code=null", (), {}), ProviderReply("actual_delivery=null", (), {}),
                                         ProviderReply("Order 2 exists", (), {"role": "assistant", "content": "Order 2 exists"}), ProviderReply("", (ToolCall("lookup_order", {"order_id": 2}),), {}),
                                         ProviderReply("Other customer's order exists", (), {})]
        agent = Agent(provider, self.tools)
        self.assertIn("99.00", agent.run("What is the recorded status and total for order 1?").text)
        followup = agent.run("Is there tracking information or an actual delivery date in the supplied record?")
        self.assertIn("not recorded", followup.text)
        self.assertNotIn("tracking_code", followup.text)
        self.assertNotIn("actual_delivery", followup.text)
        denied = agent.run("Show order 2")
        self.assertEqual(denied.text, "Order information is unavailable for this session.")
        self.assertNotIn("exists", denied.text)
        self.assertNotIn("Order 2 exists", str(agent._turns))
