"""CLI/conversation contract tests with fake providers; no genuine LLM output."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.agent import Agent
from tests.helpers import mock_shop_scope
from app.cli import main
from app.cloud_privacy import project_synthetic_question
from app.providers import GeminiProvider, ProviderConfig, ProviderReply, ToolCall
from app.synthetic import QUESTIONS, SyntheticTools
from tests.helpers import fixture_rows, write_fixture
from tests.policy_helpers import synthetic_pages, write_pdf
from tests.test_providers import gemini_config, gemini_reply


def call(name="get_price_quote", arguments=None):
    return ProviderReply("", (ToolCall(name, arguments or {"product_id": 1, "payment_method": "pix"}),),
                         {"role": "assistant", "content": "", "tool_calls": [{"function": {
                             "name": name, "arguments": arguments or {"product_id": 1, "payment_method": "pix"}}}]})


def answer(text):
    return ProviderReply(text, (), {"role": "assistant", "content": text})


class ConversationTests(unittest.TestCase):
    def setUp(self):
        mock_shop_scope(self)
        self.tools = SyntheticTools()
        self.addCleanup(self.tools.close)

    def test_greetings_are_local_and_do_not_invent_store_facts(self):
        provider = Mock(external=False)
        agent = Agent(provider, self.tools)
        self.assertEqual(agent.run("Oi!").status, "answered")
        self.assertIn("instruments", agent.run("Hello").text)
        provider.complete.assert_not_called()

    def test_arbitrary_local_questions_and_contextual_followups(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [call(), answer("Recorded price: 90.09"), answer("That promotional price already excludes PIX stacking.")]
        agent = Agent(provider, self.tools)
        self.assertEqual(agent.run("Please check the nylon instrument's PIX price").status, "answered")
        result = agent.run("Does that include the other discount?")
        self.assertEqual(result.status, "answered")
        history = provider.complete.call_args.args[0]
        self.assertEqual(history[0]["content"], "Please check the nylon instrument's PIX price")
        self.assertTrue(any(m["role"] == "tool" for m in history))
        self.assertEqual([m["content"] for m in history if m["role"] == "user"][-1], "Does that include the other discount?\n\nPlease respond in English.")

    def test_reset_and_separate_agents_do_not_rebind_identity_or_share_history(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [call(), answer("Recorded price"), answer("No evidence")]
        agent = Agent(provider, self.tools)
        agent.run("Synthetic first")
        agent.reset()
        self.assertEqual(agent.run("Synthetic after reset").status, "unverified")
        self.assertEqual(provider.complete.call_args.args[0], [{"role": "user", "content": "Synthetic after reset\n\nPlease respond in English."}])
        self.assertEqual(self.tools.execute("lookup_order", {"order_id": 1})["data"]["status"], "available")
        self.assertEqual(self.tools.execute("lookup_order", {"order_id": 2})["data"]["status"], "unavailable")
        second = Agent(Mock(external=False, complete=Mock(return_value=answer("No evidence"))), self.tools)
        self.assertEqual(second.run("Independent conversation").status, "unverified")

    def test_history_prunes_whole_exchanges_and_is_bounded(self):
        provider = Mock(external=False)
        provider.complete.side_effect = lambda history, tools, system: call() if history[-1]["role"] == "user" else answer("Snapshot price")
        agent = Agent(provider, self.tools)
        for i in range(8):
            self.assertEqual(agent.run(f"Synthetic question {i}").status, "answered")
        self.assertLessEqual(len(agent._turns), 4)
        for exchange in agent._turns:
            self.assertEqual(exchange[0]["role"], "user")
            self.assertEqual(exchange[-1]["role"], "assistant")
            self.assertEqual(sum(m["role"] == "tool" for m in exchange), 1)

    def test_cloud_freeform_is_projected_not_forwarded_verbatim(self):
        raw = "Quero comparar o preço do violão 1 com o 3. UnknownPrivateCanary"
        projected = project_synthetic_question(raw)
        self.assertIsNotNone(projected)
        self.assertNotIn("UnknownPrivateCanary", projected)
        transport = Mock(side_effect=[gemini_reply([{"functionCall": {"name": "search_products", "args": {}}}]),
                                     gemini_reply([{"text": "Synthetic catalog result"}]),
                                     gemini_reply([{"text": "Synthetic previous results"}])])
        agent = Agent(GeminiProvider(gemini_config(), transport), self.tools)
        self.assertEqual(agent.run(raw).status, "answered")
        self.assertEqual(agent.run("E qual desses está disponível?").status, "answered")
        for request in transport.call_args_list:
            outbound = json.dumps(request.args[1], ensure_ascii=False)
            self.assertNotIn(raw, outbound)
            self.assertNotIn("UnknownPrivateCanary", outbound)
            self.assertNotIn("demo-1@example.invalid", outbound)
        self.assertGreater(len(transport.call_args.args[1]["contents"]), 1)

    def test_cloud_identifiers_are_blocked_and_unknown_tokens_are_removed(self):
        for value in ("Meu nome é Alice, pedido 1", "CPF 12345678901", "email private@example.invalid", "telefone (11) 98765-4321"):
            self.assertIsNone(project_synthetic_question(value))
        self.assertNotIn("UnapprovedName", project_synthetic_question("preco UnapprovedName 1"))
        self.assertIsNone(project_synthetic_question("entire internal document please"))

    def test_approved_fixture_is_packaged_and_modifications_are_rejected(self):
        self.assertEqual(len(self.tools._catalog.repository.products), 3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixtures"
            path.mkdir()
            (path / "synthetic.json").write_text("{}", encoding="utf-8")
            with patch("app.synthetic.files", return_value=Path(directory)):
                with self.assertRaisesRegex(ValueError, "approved content"):
                    SyntheticTools()

    def test_cli_interactive_synthetic_conversation_reset_and_quit(self):
        provider = Mock(external=False)
        provider.complete.side_effect = [call(), answer("Synthetic price"), answer("Synthetic follow-up")]
        output = []
        with patch.dict("os.environ", {"LLM_PROVIDER": "ollama", "LLM_MODEL": "qwen3:4b"}):
            code = main([], input_fn=Mock(side_effect=["Quanto custa o violão de nylon?", "E com desconto?", "/reset", "/quit"]),
                        output_fn=output.append, provider_factory=lambda config: provider)
        self.assertEqual(code, 0)
        self.assertTrue(any("Synthetic follow-up" in line for line in output))
        self.assertTrue(any("identity unchanged" in line for line in output))

    def test_cli_local_data_arbitrary_input_and_bound_order_service(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            write_fixture(path, fixture_rows())
            policy = path / "test-policy.pdf"
            write_pdf(policy, synthetic_pages())
            provider = Mock(external=False)
            provider.complete.side_effect = [call("lookup_order", {"order_id": 1}), answer("Recorded order")]
            output = []
            with patch.dict("os.environ", {"LLM_PROVIDER": "ollama", "LLM_MODEL": "qwen3:4b"}):
                code = main(["--data-mode", "local", "--data-dir", str(path), "--policy-path", str(policy),
                             "--enable-demo-identity", "--demo-customer-id", "1"],
                            input_fn=Mock(side_effect=["I need help with my existing order", "/quit"]), output_fn=output.append,
                            provider_factory=lambda config: provider)
            self.assertEqual(code, 0)
            result = next(m['result'] for m in reversed(provider.complete.call_args.args[0]) if m['role'] == 'tool')
            self.assertEqual(result["data"]["status"], "available")
            self.assertEqual(result["data"]["order"]["total_brl"], "99.00")

    def test_cli_cloud_rejects_local_files_before_loading_or_network(self):
        factory = Mock()
        env = {"LLM_PROVIDER": "gemini", "LLM_MODEL": "gemini-3.1-flash-lite",
               "GEMINI_API_KEY": "synthetic-key-not-real", "GEMINI_FREE_TIER_CONFIRMED": "1"}
        with patch.dict("os.environ", env), patch("app.cli.Repository") as repository:
            code = main(["--data-mode", "local"], output_fn=Mock(), provider_factory=factory)
        self.assertEqual(code, 2)
        repository.assert_not_called()
        factory.assert_not_called()

    def test_cli_missing_local_files_and_illegal_demo_identity_fail_clearly(self):
        with patch.dict("os.environ", {"LLM_PROVIDER": "ollama", "LLM_MODEL": "qwen3:4b"}):
            with tempfile.TemporaryDirectory() as directory:
                self.assertEqual(main(["--data-mode", "local", "--data-dir", directory], output_fn=Mock()), 2)
            self.assertEqual(main(["--demo-customer-id", "2"], output_fn=Mock()), 2)

    def test_cli_eof_and_interrupt_are_clean(self):
        with patch.dict("os.environ", {"LLM_PROVIDER": "ollama", "LLM_MODEL": "qwen3:4b"}):
            self.assertEqual(main([], input_fn=Mock(side_effect=EOFError), output_fn=Mock(), provider_factory=lambda config: Mock(external=False)), 0)
            provider = Mock(external=False, complete=Mock(side_effect=KeyboardInterrupt))
            self.assertEqual(main([], input_fn=Mock(return_value="A question"), output_fn=Mock(), provider_factory=lambda config: provider), 130)

    def test_timeout_and_output_settings_are_validated(self):
        config = ProviderConfig.from_environment({"LLM_PROVIDER": "ollama", "LLM_TIMEOUT_SECONDS": "120", "LLM_MAX_OUTPUT_TOKENS": "2048"})
        self.assertEqual(config.timeout_seconds, 120)
        with self.assertRaises(ValueError):
            ProviderConfig.from_environment({"LLM_PROVIDER": "ollama", "LLM_TIMEOUT_SECONDS": "not-an-integer"})
