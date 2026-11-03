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
from app.providers import OllamaProvider, ProviderConfig, ProviderReply, ToolCall
from app.repository import Repository, SCHEMAS
from app.services import CatalogService
from app.tool_runtime import ToolRuntime
from app.conversation import product_followup
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
        steel = dict(rows["products"][0], product_id="7", category_id="1", name="Violão Sintético Aço",
                     description="Synthetic steel-string guitar", price_brl="250", stock_quantity="5",
                     specs='{"strings":"steel"}')
        rows["products"].extend((ukulele, steel))
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

    def test_multi_product_queries_precede_unique_material_matches(self):
        for question in (
                "Quais violões de nylon estão registrados?",
                "Mostre as opções de violões com cordas de aço.",
                "Quais ukuleles estão disponíveis?"):
            with self.subTest(question=question):
                self.assertEqual(self.tools.required_evidence(question), "search_products")
        for question in ("No catálogo de vocês, quais violões de nylon estão registrados?",
                         "Quais violões de nylon aparecem no catálogo?"):
            with self.subTest(search_phrase=question):
                arguments = self.tools.prepare_arguments("search_products", {"query": "invented"}, question)
                self.assertEqual(arguments["query"], "nylon")
                data = self.tools.execute("search_products", arguments)["data"]
                self.assertEqual([product["name"] for product in data["products"]], ["Test Nylon"])
        self.assertEqual(self.tools.required_evidence("Qual é o estoque do produto ID 1?"), "get_product")
        self.assertFalse(product_followup(
            "Que quantidade está marcada no estoque?"))
        self.assertTrue(product_followup("Esta, qual é o estoque?"))

    def test_steel_followup_uses_explicit_material_instead_of_previous_nylon_id(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply("", (ToolCall("get_product", {"product_id": 1}),), {}),
            ProviderReply("Nylon item", (), {}),
            ProviderReply("", (ToolCall("get_product", {"product_id": 1}),), {}),
            ProviderReply("Stale nylon answer", (), {}),
        ]
        events = []
        agent = Agent(provider, self.tools, observer=events.append)
        agent.run("Qual é o estoque do produto ID 1?")
        result = agent.run("Mudando para o violão com cordas de aço: que quantidade está marcada no estoque?")
        self.assertEqual(result.status, "answered")
        call = [event for event in events if event.get("event") == "tool_result"][-1]
        self.assertEqual(call["name"], "get_product")
        self.assertEqual(call["effective_arguments"]["product_id"], 7)
        self.assertIn("Violão Sintético Aço", result.text)
        self.assertIn("5 unidades", result.text)

    def test_explicit_steel_descriptor_overrides_previous_nylon_selection(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply("", (ToolCall("get_product", {"product_id": 1}),), {}),
            ProviderReply("Nylon item", (), {}),
            # Deliberately stale model argument: deterministic resolution must
            # replace it with the uniquely named steel-string catalog item.
            ProviderReply("", (ToolCall("get_product", {"product_id": 1}),), {}),
            ProviderReply("Stale nylon answer", (), {}),
        ]
        events = []
        agent = Agent(provider, self.tools, observer=events.append)
        agent.run("Qual é o estoque do produto ID 1?")
        result = agent.run("Esse de aço, qual estoque?")
        self.assertEqual(result.status, "answered")
        call = [event for event in events if event.get("event") == "tool_result"][-1]
        self.assertEqual(call["name"], "get_product")
        self.assertEqual(call["effective_arguments"]["product_id"], 7)
        self.assertIn("Violão Sintético Aço", result.text)

    def test_named_purchase_with_quantity_resolves_current_turn_product(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply("", (ToolCall("get_product", {"product_id": 7}),), {}),
            ProviderReply("Draft", (), {}),
        ]
        events = []
        agent = Agent(provider, self.tools, observer=events.append)

        result = agent.run("Tenho interesse em comprar duas unidades do violão de nylon. O estoque cobre?")

        tool = next(event for event in events if event.get("event") == "tool_result")
        self.assertEqual(tool["effective_arguments"]["product_id"], 1)
        self.assertIn("Test Nylon", result.text)
        self.assertIn("O cadastro registra 2 unidades", result.text)
        self.assertIn("não reserva o estoque", result.text)

    def test_explicit_two_product_comparison_overrides_previous_product(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply("", (ToolCall("get_price_quote", {"product_id": 7}),
                                ToolCall("get_price_quote", {"product_id": 1})), {}),
            ProviderReply("Draft comparison", (), {}),
        ]
        events = []
        agent = Agent(provider, self.tools, observer=events.append)
        agent._last_product_ids = (7,)

        result = agent.run("Compare os violões de nylon e aço disponíveis, incluindo os preços.")

        lookups = [event["effective_arguments"]["product_id"] for event in events
                   if event.get("event") == "tool_result" and event.get("name") == "get_price_quote"]
        self.assertEqual(set(lookups), {1, 7})
        self.assertEqual(len(lookups), 2)
        self.assertIn("Test Nylon", result.text)
        self.assertIn("Violão Sintético Aço", result.text)

    def test_duplicate_successful_tool_calls_are_reused_only_within_one_turn(self):
        provider = Mock(external=False)
        repeated = ProviderReply("", (ToolCall("get_price_quote", {"product_id": 1}),
                                       ToolCall("get_price_quote", {"product_id": 1})), {})
        provider.complete.side_effect = [repeated, ProviderReply("Draft", (), {}),
                                         repeated, ProviderReply("Draft", (), {})]
        events = []
        agent = Agent(provider, self.tools, observer=events.append)
        agent._deterministic_catalog_plan = lambda question: None
        execute = Mock(wraps=self.tools.execute)
        self.tools.execute = execute

        first = agent.run("Qual o preço do produto ID 1?")
        second = agent.run("Qual o preço do produto ID 1?")

        self.assertEqual(execute.call_count, 2)
        self.assertEqual(first.tools_called, ("get_price_quote",))
        self.assertEqual(second.tools_called, ("get_price_quote",))
        self.assertEqual(sum(e.get("event") == "tool_cache_reuse" for e in events), 2)
        self.assertEqual(sum(e.get("event") == "tool_result" and e.get("name") == "get_price_quote"
                             for e in events), 2)
        self.assertEqual(first.text.count("Test Nylon"), 1)
        self.assertEqual(second.text.count("Test Nylon"), 1)

    def test_distinct_policy_queries_do_not_share_cached_evidence(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply("", (ToolCall("search_policies", {"query": "garantia"}),
                                ToolCall("search_policies", {"query": "frete"})), {}),
            ProviderReply("Draft", (), {}),
        ]
        execute = Mock(wraps=self.tools.execute)
        self.tools.execute = execute
        agent = Agent(provider, self.tools)

        result = agent.run("Quais são as condições de garantia e frete?")

        self.assertEqual(execute.call_count, 2)
        self.assertEqual(result.tools_called.count("search_policies"), 2)

    def test_exact_catalog_facts_use_grounded_python_fast_path(self):
        price_transport = Mock()
        price_provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b-instruct"), price_transport)
        price_agent = Agent(price_provider, self.tools)
        price = price_agent.run("Qual o preço do produto ID 1 no Pix?")
        self.assertEqual(price.status, "answered")
        self.assertEqual(price.tools_called, ("get_price_quote",))
        self.assertIn("R$ 90,09", price.text)
        price_transport.assert_not_called()

        stock_transport = Mock()
        stock_agent = Agent(OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b-instruct"),
                                           stock_transport), self.tools)
        stock = stock_agent.run("Qual é o estoque do produto ID 7?")
        self.assertEqual(stock.tools_called, ("get_product",))
        self.assertIn("Estoque registrado: 5 unidades", stock.text)
        stock_transport.assert_not_called()

        purchase_transport = Mock()
        purchase_agent = Agent(OllamaProvider(
            ProviderConfig(provider="ollama", model="qwen3:4b-instruct"), purchase_transport), self.tools)
        purchase = purchase_agent.run(
            "Tenho interesse em comprar duas unidades do violão de nylon. O estoque cobre?")
        self.assertIn("O cadastro registra 2 unidades", purchase.text)
        self.assertIn("as 2 unidades que você quer estão cobertas", purchase.text)
        self.assertIn("não reserva o estoque nem cria um pedido", purchase.text)
        purchase_transport.assert_not_called()

        invalid_transport = Mock()
        invalid_agent = Agent(OllamaProvider(
            ProviderConfig(provider="ollama", model="qwen3:4b-instruct"), invalid_transport), self.tools)
        invalid = invalid_agent.run("Qual é o estoque do produto ID 999?")
        self.assertEqual(invalid.status, "tool_error")
        self.assertIn("product identifier was not found", invalid.text)
        invalid_transport.assert_not_called()

    def test_explicit_multi_product_price_comparison_uses_distinct_quotes(self):
        transport = Mock()
        provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b-instruct"), transport)
        events = []
        agent = Agent(provider, self.tools, observer=events.append)
        agent._last_product_ids = (7,)

        result = agent.run("Compare o preço do produto ID 1 e do produto ID 7.")

        quotes = [e for e in events if e.get("event") == "tool_result"]
        self.assertEqual([e["effective_arguments"]["product_id"] for e in quotes], [1, 7])
        self.assertEqual(result.tools_called, ("get_price_quote", "get_price_quote"))
        self.assertIn("Test Nylon", result.text)
        self.assertIn("Violão Sintético Aço", result.text)
        transport.assert_not_called()

    def test_deictic_comparison_keeps_selected_and_explicit_products_and_answers_list_price(self):
        transport = Mock()
        provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b-instruct"), transport)
        events = []
        agent = Agent(provider, self.tools, observer=events.append)

        agent.run("Qual é o preço de tabela do Test Nylon?")
        agent.run("Mudando para Violão Sintético Aço, quanto fica no PIX?")
        answer = agent.run("Comparando esse com o nylon, qual tem menor preço de tabela?")

        quotes = [event for event in events if event.get('event') == 'tool_result'
                  and event.get('name') == 'get_price_quote']
        self.assertEqual([event['effective_arguments']['product_id'] for event in quotes[-2:]], [7, 1])
        self.assertIn('Test Nylon', answer.text)
        self.assertIn('Violão Sintético Aço', answer.text)
        self.assertIn('preço de tabela: R$ 100,10', answer.text)
        self.assertIn('preço de tabela: R$ 250,00', answer.text)
        self.assertIn('menor preço de tabela', answer.text.casefold())
        self.assertIn('R$ 90,09', answer.text)  # The active promotion remains separate from list price.
        transport.assert_not_called()

    def test_plural_comparison_uses_two_recent_verified_products(self):
        transport = Mock()
        provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b-instruct"), transport)
        events = []
        agent = Agent(provider, self.tools, observer=events.append)

        agent.run("Qual é o preço do Test Nylon?")
        agent.run("E quanto custa o Violão Sintético Aço?")
        result = agent.run("Compara os dois pelo preço de tabela.")

        quotes = [event for event in events if event.get('event') == 'tool_result'
                  and event.get('name') == 'get_price_quote']
        self.assertEqual({event['effective_arguments']['product_id'] for event in quotes[-2:]}, {1, 7})
        self.assertIn('preço de tabela: R$ 100,10', result.text)
        self.assertIn('preço de tabela: R$ 250,00', result.text)
        transport.assert_not_called()

    def test_catalog_browsing_and_policy_questions_stay_outside_product_fast_path(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [
            ProviderReply("", (ToolCall("search_products", {"query": "violão"}),), {}),
            ProviderReply("Encontrei opções no catálogo.", (), {}),
            ProviderReply("", (ToolCall("search_policies", {"query": "devolução"}),), {}),
            ProviderReply("A política permite solicitar em até sete dias. Fonte: seção 4.1, página 8.", (), {}),
        ]
        agent = Agent(provider, self.tools)

        catalog = agent.run("Quais violões estão disponíveis?")
        policy = agent.run("Qual o prazo para devolução online?")

        self.assertIn("search_products", catalog.tools_called)
        self.assertIn("search_policies", policy.tools_called)
        self.assertEqual(provider.complete.call_count, 4)

    def test_mixed_price_and_recommendation_turn_stays_on_model_path(self):
        transport = Mock()
        provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b-instruct"), transport)
        provider.complete = Mock(side_effect=[
            ProviderReply("", (ToolCall("get_price_quote", {"product_id": 1}),), {}),
            ProviderReply("O produto custa R$ 90,09. Para recomendar melhor, preciso saber o que você pretende tocar.", (), {}),
        ])
        events = []
        agent = Agent(provider, self.tools, observer=events.append)

        result = agent.run("Qual é o preço do produto ID 1 e qual instrumento você recomenda para começar?")

        self.assertEqual(provider.complete.call_count, 2)
        self.assertFalse(any(event.get("event") == "deterministic_fast_path" for event in events))
        self.assertEqual(result.status, "answered")

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
        agent.run("Get product ID 6")
        result = agent.run("Quais violões até R$150? Quero todos os modelos.")
        self.assertEqual(result.status, "answered")
        self.assertNotIn("Ukulele", result.text)
        self.assertEqual(sum(line[:1].isdigit() for line in result.text.splitlines()), 9)

    def test_partial_list_is_never_rendered_as_complete(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [ProviderReply("", (ToolCall("search_products", {"query": "violão", "max_price_brl": "150"}),), {}), ProviderReply("This is the complete catalog", (), {})]
        result = Agent(provider, self.tools).run("Quais violões até R$150?")
        # Searches return the full sorted set (the UI paginates); the model's claim is not echoed.
        self.assertIn("9 opções", result.text)
        self.assertNotIn("This is the complete catalog", result.text)
        # A result truncated by the output ceiling is still labelled partial.
        from app.grounding import render_catalog
        args = self.tools.prepare_arguments("search_products", {}, "Quais violões até R$150?")
        data = self.tools.execute("search_products", args)["data"]
        data.update(products=data["products"][:5], returned_count=5, truncated=True)
        text = render_catalog(data, self.tools._catalog.repository.categories)
        self.assertIn("5 de 9", text)
        self.assertIn("parcial", text.casefold())


@unittest.skipUnless(all((DATA / f"{name}.csv").is_file() for name in SCHEMAS), "Authorized original CSVs absent")
class OriginalCatalogRegressionTests(unittest.TestCase):
    def test_exact_reported_query_returns_twelve_in_stock_acoustic_guitars(self):
        repo = Repository(DATA)
        products = CatalogService(repo).search_products("violão", max_price_brl=Decimal("1000"))
        self.assertEqual([p.product_id for p in products], [83, 85, 89, 88, 81, 84, 87, 86, 107, 82, 91, 112])
        self.assertTrue(all(p.category_id == 5 and p.available for p in products))
        self.assertNotIn(128, {p.product_id for p in products})
