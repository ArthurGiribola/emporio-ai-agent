"""Exact desktop questions; mocked argument faults are not live-model recordings."""
import unittest
from unittest.mock import Mock, patch
from app.agent import Agent
from app.providers import ProviderReply, ToolCall
from app.synthetic import SyntheticTools

QUESTIONS = ["Quais produtos sintéticos estão disponíveis? Liste todos do mais barato ao mais caro.",
             "Me dê uma lista de todos os produtos pf."]

class DesktopCatalogTests(unittest.TestCase):
    def test_exact_multiturn_requests_discard_stale_filters_and_generic_words(self):
        with SyntheticTools() as tools:
            provider = Mock(external=False)
            provider.complete.side_effect = [
                ProviderReply("", (ToolCall("search_products", {"query":"ukulele", "max_price_brl":"1000"}),), {}), ProviderReply("none", (), {}),
                ProviderReply("", (ToolCall("search_products", {"query":"sintéticos", "category_id":9, "max_price_brl":"1000"}),), {}), ProviderReply("none", (), {}),
                ProviderReply("", (ToolCall("search_products", {"query":"lista de todos os produtos pf", "category_id":9, "max_price_brl":"10"}),), {}), ProviderReply("none", (), {})]
            events=[]; agent=Agent(provider,tools,observer=events.append)
            agent.run("Quais ukuleles até R$1000?")
            for question in QUESTIONS:
                events.clear(); result=agent.run(question)
                self.assertEqual(result.status,"answered")
                event=next(e for e in events if e["event"]=="tool_result")
                data=event["result"]["data"]
                self.assertEqual(data["total_matches"],2)
                self.assertEqual(data["returned_count"],2)
                self.assertFalse(data["truncated"])
                self.assertEqual([p["effective_price_brl"] for p in data["products"]],["90.09","250.00"])
                self.assertNotIn("max_price_brl",event["effective_arguments"])
                self.assertNotIn("category_id",event["effective_arguments"])
                self.assertNotIn("Não encontrei",result.text)

    def test_explicit_filters_remain_and_effective_price_controls_sort(self):
        from decimal import Decimal
        from dataclasses import replace
        with SyntheticTools() as tools:
            args=tools.prepare_arguments("search_products",{"query":"", "category_id":9},"Todos os violões até R$150 com preço final")
            self.assertEqual(args["category_id"],1)
            self.assertEqual(args["max_price_brl"],"150")
            repo=tools._catalog.repository
            products=dict(repo.products)
            products[3]=replace(products[3], price_brl=Decimal("95.00"))
            with patch.object(repo, "products", products):
                data=tools.execute("search_products",{"all_results":True,"sort_by":"effective_price"})["data"]
            self.assertEqual([p["product_id"] for p in data["products"]],[1,3])

    def test_empty_dataset_no_matches_and_errors_are_distinct(self):
        with SyntheticTools() as tools:
            no=tools.execute("search_products",{"query":"no-such-model"})
            self.assertEqual(no["data"]["catalog_state"],"no_matches")
            error=tools.execute("search_products",{"max_price_brl":"broken"})
            text=tools.grounded_answer(QUESTIONS[0],[("search_products",error)],"Não encontrei produtos")
            self.assertIn("falhou",text)
            self.assertNotIn("Não encontrei",text)
            with patch.object(tools._catalog.repository, "products", {}):
                empty=tools.execute("search_products",{})
            self.assertEqual(empty["data"]["catalog_state"],"empty_dataset")
            self.assertIn("vazio",tools.grounded_answer(QUESTIONS[0],[("search_products",empty)],""))
