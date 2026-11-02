"""Catalog correctness regressions: synthetic fixtures and optional original data."""

import os
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app.agent import Agent
from tests.helpers import mock_shop_scope
from app.orders import OrderService
from app.policies import PolicyRetriever
from app.providers import ProviderReply, ToolCall
from app.repository import Repository, SCHEMAS
from app.services import CatalogService
from app.tool_runtime import ToolRuntime
from tests.helpers import fixture_rows, write_fixture
from tests.policy_helpers import synthetic_pages, write_pdf


QUESTION = "Existem outros violões disponíveis por até R$ 1.000? Quero ver todos os modelos, do mais barato para o mais caro."
DATA = Path(os.environ.get("EMPORIO_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


class CatalogRegressionTests(unittest.TestCase):
    def setUp(self):
        mock_shop_scope(self)
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name)
        rows = fixture_rows()
        ukulele = dict(rows["products"][0], product_id="6", category_id="2", name="Synthetic Baritone Ukulele",
                       description="Uma ponte entre o ukulele e o violão", price_brl="99")
        rows["products"].append(ukulele)
        for i in range(10, 17):
            rows["products"].append(dict(rows["products"][0], product_id=str(i), name=f"Synthetic Model {i}", price_brl=str(100 + i)))
        write_fixture(path, rows)
        write_pdf(path / "policy.pdf", synthetic_pages())
        self.repo = Repository(path)
        self.tools = ToolRuntime(self.repo, PolicyRetriever(path / "policy.pdf"), OrderService(self.repo))

    def test_category_words_do_not_match_another_category_description(self):
        products = CatalogService(self.repo).search_products("violão", max_price_brl=Decimal("150"))
        self.assertEqual(len(products), 9)
        self.assertTrue(all(p.category_id == 1 and p.available for p in products))
        self.assertNotIn(6, {p.product_id for p in products})

    def test_all_results_and_partial_metadata_are_truthful(self):
        result = self.tools.execute("search_products", {"query": "violão", "max_price_brl": "150", "all_results": True})
        self.assertEqual(result["status"], "ok")
        data = result["data"]
        self.assertEqual((len(data["products"]), data["total_matches"], data["returned_count"]), (9, 9, 9))
        self.assertFalse(data["truncated"])
        self.assertEqual([Decimal(p["list_price_brl"]) for p in data["products"]], sorted(Decimal(p["list_price_brl"]) for p in data["products"]))
        partial = self.tools.execute("search_products", {"query": "violão", "max_price_brl": "150"})["data"]
        self.assertEqual(partial["returned_count"], 5)
        self.assertEqual(partial["total_matches"], 9)
        self.assertTrue(partial["truncated"])

    def test_model_category_and_output_cannot_override_explicit_customer_filters(self):
        observer = Mock()
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("search_products", {"query": "ukulele", "category_id": 2, "max_price_brl": "9999", "all_results": False}),), {}),
                                         ProviderReply("Here are all five ukuleles, list_price_brl=99", (), {})]
        agent = Agent(provider, self.tools, observer=observer)
        result = agent.run("Quais violões até R$ 150? Quero todos, do mais barato ao mais caro.")
        self.assertNotIn("Ukulele", result.text)
        self.assertNotIn("list_price_brl", result.text)
        self.assertIn("9", result.text)
        self.assertEqual(sum(line[:1].isdigit() for line in result.text.splitlines()), 9)
        event = next(c.args[0] for c in observer.call_args_list if c.args[0]["event"] == "tool_result")
        self.assertEqual(event["requested_arguments"]["category_id"], 2)
        self.assertEqual(event["effective_arguments"]["category_id"], 1)
        self.assertEqual(event["result"]["data"]["total_matches"], 9)

    def test_explicit_all_request_requires_fresh_search_instead_of_old_context(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("get_product", {"product_id": 6}),), {}), ProviderReply("Prior ukulele result", (), {}),
                                         ProviderReply("Here are five old products", (), {}),
                                         ProviderReply("", (ToolCall("search_products", {"query": "violão", "max_price_brl": "150"}),), {}), ProviderReply("Incomplete prose", (), {})]
        agent = Agent(provider, self.tools)
        agent.run("Get product 6")
        result = agent.run("Quais violões até R$150? Quero todos os modelos.")
        self.assertEqual(result.status, "answered")
        self.assertNotIn("Ukulele", result.text)
        self.assertEqual(sum(line[:1].isdigit() for line in result.text.splitlines()), 9)

    def test_default_partial_list_is_never_rendered_as_complete(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("search_products", {"query": "violão", "max_price_brl": "150"}),), {}), ProviderReply("This is the complete catalog", (), {})]
        result = Agent(provider, self.tools).run("Quais violões até R$150?")
        self.assertIn("5 de 9", result.text)
        self.assertIn("parcial", result.text.casefold())


@unittest.skipUnless(all((DATA / f"{name}.csv").is_file() for name in SCHEMAS), "Authorized original CSVs absent")
class OriginalCatalogRegressionTests(unittest.TestCase):
    def test_exact_reported_query_returns_twelve_in_stock_acoustic_guitars(self):
        repo = Repository(DATA)
        products = CatalogService(repo).search_products("violão", max_price_brl=Decimal("1000"))
        self.assertEqual([p.product_id for p in products], [83, 85, 89, 88, 81, 84, 87, 86, 107, 82, 91, 112])
        self.assertTrue(all(p.category_id == 5 and p.available for p in products))
        self.assertNotIn(128, {p.product_id for p in products})
