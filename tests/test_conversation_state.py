"""Multi-turn customer-service flows over the per-session conversation state.

Fictional 65-product catalog; real ChatSession and services; the model is the
scripted cooperative stub from scripts/task_eval.py, so these tests check the
orchestration and state, not model quality.
"""

import re
import unittest

from scripts.task_eval import Run, fixture_environment

FULL = "Liste o catálogo completo, incluindo produtos indisponíveis e inativos, do mais barato ao mais caro."
NO_ORDER = "não reserva o estoque nem cria um pedido"
PURCHASE_CLAIM = re.compile(r"compra (?:foi )?(?:realizada|finalizada|concluída|confirmada)|reservei|pedido (?:criado|realizado)", re.I)


class ConversationStateFlows(unittest.TestCase):
    def setUp(self):
        self._env = fixture_environment()
        self.env = self._env.__enter__()
        self.addCleanup(self._env.__exit__, None, None, None)

    def session(self):
        run = Run(self.env, stub="oracle")
        self.addCleanup(run.session.close)
        return run

    def say(self, run, text, calls=(), reply="Certo!"):
        run.oracle.turn = {"calls": [dict(c) for c in calls], "text": reply}
        run.events.clear()
        answer = run.session.ask(text)
        if answer.catalog is not None and answer.catalog.entries:
            run.displayed = tuple(e.product_id for e in answer.catalog.entries)
        self.assertFalse(PURCHASE_CLAIM.search(answer.text), answer.text)
        return answer

    def looked_up(self, run):
        return [e["effective_arguments"].get("product_id") for e in run.events
                if e.get("event") == "tool_result" and e["name"] in {"get_product", "get_price_quote"}]

    def select(self, run, position):
        self.say(run, FULL, [{"name": "search_products", "arguments": {"scope": "browse"}}])
        product_id = run.displayed[position - 1]
        run.session.select_product(product_id)
        run.selected = product_id
        name = run.catalog.get_product(product_id).name
        card = self.say(run, f"Quero saber mais sobre o item {position}: {name}.",
                        [{"name": "get_product", "arguments": {"product_id": product_id}}])
        return product_id, name, card

    def test_purchase_without_product_shows_options_and_asks_which(self):
        run = self.session()
        answer = self.say(run, "quero comprar um ukulele")
        self.assertIsNotNone(answer.catalog)
        names = {run.catalog.repository.categories[run.catalog.get_product(e.product_id).category_id].name
                 for e in answer.catalog.entries}
        self.assertEqual(names, {"Ukuleles"})
        self.assertIn("?", answer.text)
        self.assertNotIn("lookup_order", answer.tools_called if hasattr(answer, "tools_called") else ())

    def test_purchase_of_selected_product_asks_quantity_without_repeating_the_card(self):
        run = self.session()
        product_id, name, card = self.select(run, 5)
        self.assertIn("Estoque registrado", card.text)
        answer = self.say(run, "gostaria de comprar ele porfavor")
        self.assertIn(name, answer.text)
        self.assertRegex(answer.text, r"Quantas unidades")
        self.assertNotIn("Categoria:", answer.text)
        self.assertEqual(self.looked_up(run), [product_id])

    def test_quantity_only_continuation_checks_stock(self):
        run = self.session()
        product_id, name, _ = self.select(run, 5)
        stock = run.catalog.get_product(product_id).stock_quantity
        self.say(run, "quero levar esse")
        for continuation in ("2", "vou querer 2", "2 unidades"):
            with self.subTest(continuation=continuation):
                answer = self.say(run, continuation)
                self.assertEqual(self.looked_up(run), [product_id])
                self.assertIn("2 unidades", answer.text)
                self.assertIn(f"{stock} unidades", answer.text)
                self.assertIn(NO_ORDER, answer.text)

    def test_quantity_above_stock_uses_the_selected_product_not_a_name_with_digits(self):
        run = self.session()
        product_id, name, _ = self.select(run, 7)  # stock 2
        answer = self.say(run, "quero 5 desse")
        self.assertEqual(self.looked_up(run), [product_id])
        self.assertIn(name, answer.text)
        self.assertIn("não consigo confirmar essa quantidade completa", answer.text)
        self.assertNotIn("HL-5", answer.text)

    def test_changing_product_mid_purchase_moves_the_purchase(self):
        run = self.session()
        first, _, _ = self.select(run, 5)
        self.say(run, "quero levar esse")
        other = run.displayed[7]
        other_name = run.catalog.get_product(other).name
        answer = self.say(run, f"na verdade quero comprar o {other_name}")
        self.assertEqual(self.looked_up(run), [other])
        self.assertIn(other_name, answer.text)
        self.assertRegex(answer.text, r"Quantas unidades")
        answer = self.say(run, "3 unidades")
        self.assertEqual(self.looked_up(run), [other])

    def test_followups_about_price_stock_and_pix_use_the_selected_product(self):
        run = self.session()
        product_id, name, _ = self.select(run, 5)
        for question, calls in (("quanto fica no pix?", [{"name": "get_price_quote", "arguments": {"product_id": product_id, "payment_method": "pix"}}]),
                                ("quantas tem em estoque?", [{"name": "get_product", "arguments": {"product_id": product_id}}]),
                                ("e qual o preço?", [{"name": "get_price_quote", "arguments": {"product_id": product_id}}])):
            with self.subTest(question=question):
                answer = self.say(run, question, calls)
                self.assertIn(name, answer.text)
                self.assertTrue(self.looked_up(run))
                self.assertEqual(set(self.looked_up(run)), {product_id})

    def test_reset_clears_selection_and_purchase(self):
        run = self.session()
        self.select(run, 5)
        self.say(run, "quero levar esse")
        run.session.reset()
        answer = self.say(run, "quero comprar 2")
        self.assertEqual(self.looked_up(run), [])
        self.assertIn("Quais instrumentos", answer.text)
        with self.assertRaises(ValueError):
            run.session.select_product(run.displayed[0])  # the old list is gone too

    def test_sessions_do_not_share_state(self):
        first, second = self.session(), self.session()
        self.select(first, 5)
        self.say(first, "quero levar esse")
        answer = self.say(second, "quero comprar ele")
        self.assertEqual(self.looked_up(second), [])
        self.assertIn("Quais instrumentos", answer.text)

    def test_browsing_all_options_then_keeps_the_category_just_asked_for(self):
        run = self.session()
        self.say(run, "quais ukuleles vocês têm?", [{"name": "search_products", "arguments": {"scope": "browse"}}])
        answer = self.say(run, "me mostre todas as opções então",
                          [{"name": "search_products", "arguments": {"scope": "browse", "category_id": 4}}])
        categories = {run.catalog.get_product(e.product_id).category_id for e in answer.catalog.entries}
        self.assertEqual(categories, {4})

    def test_showing_a_new_list_ends_the_purchase_of_the_previous_product(self):
        run = self.session()
        product_id, _, _ = self.select(run, 5)
        self.say(run, "quero levar esse")
        self.assertEqual(run.session._agent._state.purchase.product_id, product_id)
        answer = self.say(run, "agora quero ver os violões", [{"name": "search_products", "arguments": {"scope": "browse"}}])
        self.assertTrue(answer.catalog.entries)
        self.assertIsNone(run.session._agent._state.purchase)
        answer = self.say(run, "2")
        self.assertNotIn(product_id, self.looked_up(run))

    def test_naming_another_category_ends_the_purchase_even_if_the_turn_fails(self):
        run = self.session()
        product_id, _, _ = self.select(run, 5)
        self.say(run, "quero levar esse")
        self.assertEqual(run.session._agent._state.purchase.product_id, product_id)
        run.oracle.mode = "text"  # the model answers without a tool: this turn fails safely
        self.say(run, "na verdade quero ver os teclados")
        run.oracle.mode = "oracle"
        self.assertIsNone(run.session._agent._state.purchase)
        self.assertIsNone(run.session._agent._state.selected_id)
        answer = self.say(run, "2")
        self.assertNotIn(product_id, self.looked_up(run))
        self.assertNotIn(run.catalog.get_product(product_id).name, answer.text)

    def test_a_displayed_catalog_search_needs_no_extra_model_draft(self):
        run = self.session()
        calls = []
        transport = run.oracle.transport
        run.oracle.transport = lambda url, payload, headers, timeout: (calls.append(url), transport(url, payload, headers, timeout))[1]
        run.session._agent._provider._transport = run.oracle.transport
        answer = self.say(run, "quais ukuleles vocês têm?", [{"name": "search_products", "arguments": {"scope": "browse"}}])
        self.assertEqual(len(answer.catalog.entries), 12)
        chats = [u for u in calls if u.endswith("/api/chat")]
        self.assertEqual(len(chats), 2)  # scope check + the tool call; no discarded draft

    def test_model_category_not_requested_by_the_customer_is_ignored(self):
        run = self.session()
        answer = self.say(run, "me mostre todas as opções",
                          [{"name": "search_products", "arguments": {"scope": "browse", "category_id": 4}}])
        self.assertEqual(len(answer.catalog.entries), 59)


if __name__ == "__main__":
    unittest.main()
