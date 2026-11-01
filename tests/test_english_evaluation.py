"""Regressions for gaps observed during actual English evaluation."""

import unittest
from unittest.mock import Mock

from app.agent import Agent
from app.providers import ProviderReply, ToolCall
from app.synthetic import SyntheticTools


class EnglishEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tools = SyntheticTools()
        self.addCleanup(self.tools.close)

    def test_all_is_not_a_product_filter_and_customer_output_is_english(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("search_products", {"query": "all", "all_results": True, "max_price_brl": "10000", "category_id": 99}),), {}),
                                         ProviderReply("There are no products", (), {})]
        events = []
        result = Agent(provider, self.tools, observer=events.append).run("Please list all available products, sorted from the lowest to the highest price.")
        self.assertEqual(result.status, "answered")
        self.assertTrue(result.text.startswith("Complete list of 2"))
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
