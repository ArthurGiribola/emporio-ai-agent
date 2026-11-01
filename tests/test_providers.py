import copy
import io
import unittest
from urllib.error import HTTPError, URLError
from unittest.mock import Mock, patch

from app.providers import (ConfigurationError, GeminiProvider, OllamaProvider, ProviderConfig,
                           ProviderError, create_provider, http_json)


TOOL = {"name": "price", "description": "Synthetic price lookup", "parameters": {
    "type": "object", "properties": {"id": {"type": "integer"}},
    "required": ["id"], "additionalProperties": False}}


def gemini_config():
    return ProviderConfig(api_key="synthetic-key-not-a-real-credential", free_tier_confirmed=True)


def gemini_reply(parts):
    return {"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": parts}}]}


class ProviderTests(unittest.TestCase):
    def test_configuration_defaults_and_secret_repr(self):
        config = ProviderConfig.from_environment({"GEMINI_API_KEY": "synthetic-only", "GEMINI_FREE_TIER_CONFIRMED": "1"})
        self.assertEqual(config.model, "gemini-3.1-flash-lite")
        self.assertNotIn("synthetic-only", repr(config))
        self.assertIsInstance(create_provider(config), GeminiProvider)
        self.assertEqual(ProviderConfig.from_environment({"LLM_PROVIDER": "ollama"}).model, "qwen3:4b")

    def test_paid_unverified_missing_key_and_unconfirmed_projects_fail_closed(self):
        for arguments in ({}, {"api_key": "synthetic"}, {"free_tier_confirmed": True},
                          {"api_key": "synthetic", "free_tier_confirmed": True, "model": "paid-model"},
                          {"provider": "openai"}, {"timeout_seconds": 0}, {"max_output_tokens": 1}):
            with self.subTest(arguments=arguments), self.assertRaises(ConfigurationError):
                ProviderConfig(**arguments)

    def test_ollama_rejects_remote_cloud_and_redirectable_configuration(self):
        for base in ("https://ollama.com", "http://example.com:11434", "http://localhost:11434",
                     "http://127.0.0.1:11434/api", "http://key@127.0.0.1:11434",
                     "http://127.0.0.1:11434?key=synthetic", "http://127.0.0.1:bad"):
            with self.subTest(base=base), self.assertRaises(ConfigurationError):
                ProviderConfig(provider="ollama", model="qwen3:4b", base_url=base)
        with self.assertRaises(ConfigurationError):
            ProviderConfig(provider="ollama", model="remote:cloud")

    def test_gemini_native_function_call_and_thought_signature_round_trip(self):
        parts = [{"thought": True, "text": "Synthetic hidden thought"},
                 {"functionCall": {"name": "price", "args": {"id": 1}, "id": "call-1"},
                  "thoughtSignature": "synthetic-signature"}]
        transport = Mock(side_effect=[gemini_reply(parts), gemini_reply([{"text": "Synthetic result"}])])
        provider = GeminiProvider(gemini_config(), transport)
        history = [{"role": "user", "content": "Synthetic question"}]
        first = provider.complete(history, [TOOL], "Use tools")
        self.assertEqual(first.text, "")
        self.assertEqual(first.calls[0].arguments, {"id": 1})
        history += [{"role": "assistant", "native": first.native},
                    {"role": "tool", "name": "price", "call_id": "call-1", "result": {"price": "90.09"}}]
        second = provider.complete(history, [TOOL], "Use tools")
        self.assertEqual(second.text, "Synthetic result")
        url, payload, headers, timeout = transport.call_args.args
        self.assertEqual(payload["contents"][1]["parts"], parts)
        self.assertEqual(payload["contents"][2]["parts"][0]["functionResponse"]["id"], "call-1")
        self.assertFalse(payload["store"])
        self.assertNotIn("synthetic-key", url)
        self.assertIn("x-goog-api-key", headers)
        self.assertEqual(payload["tools"][0]["functionDeclarations"][0]["parametersJsonSchema"]["additionalProperties"], False)

    def test_parallel_gemini_results_share_one_user_turn(self):
        transport = Mock(return_value=gemini_reply([{"text": "Done"}]))
        history = [{"role": "user", "content": "Synthetic"},
                   {"role": "assistant", "native": {"role": "model", "parts": []}},
                   {"role": "tool", "name": "price", "call_id": "1", "result": {}},
                   {"role": "tool", "name": "price", "call_id": "2", "result": {}}]
        GeminiProvider(gemini_config(), transport).complete(history, [TOOL], "System")
        self.assertEqual(len(transport.call_args.args[1]["contents"][-1]["parts"]), 2)

    def test_gemini_blocked_truncated_and_malformed_responses(self):
        for response in ({}, {"candidates": []}, {"candidates": [{"finishReason": "MAX_TOKENS"}]},
                         gemini_reply([{"functionCall": {"name": "price", "args": "not an object"}}])):
            with self.subTest(response=response), self.assertRaises(ProviderError):
                GeminiProvider(gemini_config(), Mock(return_value=response)).complete([], [TOOL], "System")

    def test_ollama_checks_local_model_tools_and_native_protocol(self):
        message = {"role": "assistant", "content": "", "thinking": "Synthetic thought",
                   "tool_calls": [{"function": {"name": "price", "arguments": {"id": 1}}}]}
        transport = Mock(side_effect=[{"capabilities": ["completion", "tools"]},
                                     {"done": True, "message": message},
                                     {"done": True, "message": {"role": "assistant", "content": "Synthetic result"}}])
        provider = OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b"), transport)
        first = provider.complete([{"role": "user", "content": "Synthetic"}], [TOOL], "System")
        self.assertEqual(first.calls[0].name, "price")
        second = provider.complete([{"role": "assistant", "native": first.native},
                                    {"role": "tool", "name": "price", "call_id": "", "result": {"price": "90.09"}}], [TOOL], "System")
        self.assertEqual(second.text, "Synthetic result")
        payload = transport.call_args.args[1]
        self.assertEqual(payload["messages"][1], message)
        self.assertEqual(payload["messages"][2]["tool_name"], "price")
        self.assertFalse(payload["stream"])
        self.assertEqual(transport.call_count, 3)

    def test_ollama_missing_tool_capability_or_remote_metadata_fails(self):
        for info in ({"capabilities": ["completion"]}, {"capabilities": ["tools"], "remote_host": "external"}):
            with self.subTest(info=info), self.assertRaises(ProviderError):
                OllamaProvider(ProviderConfig(provider="ollama", model="qwen3:4b"), Mock(return_value=info)).complete([], [TOOL], "System")

    def test_http_errors_are_sanitized_without_retries(self):
        opener = Mock()
        for error in (HTTPError("https://example.invalid", 429, "secret body", {}, io.BytesIO(b"private")),
                      HTTPError("https://example.invalid", 403, "secret body", {}, io.BytesIO(b"private")),
                      URLError("private failure details"), TimeoutError("private timeout")):
            with self.subTest(error_type=type(error).__name__):
                opener.open.reset_mock()
                opener.open.side_effect = error
                with patch("app.providers.build_opener", return_value=opener):
                    with self.assertRaises(ProviderError) as captured:
                        http_json("https://example.invalid", {}, {}, 1)
                self.assertNotIn("private", str(captured.exception))
                self.assertNotIn("secret", str(captured.exception))
                opener.open.assert_called_once()

    def test_http_serialization_bounded_response_and_no_redirect_handler(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock()
        opener.open.return_value = response
        response.read.return_value = b'{"ok":true}'
        with patch("app.providers.build_opener", return_value=opener) as builder:
            self.assertEqual(http_json("http://127.0.0.1:11434", {"question": "sintético"}, {}, 2), {"ok": True})
            self.assertEqual(len(builder.call_args.args), 2)
            request = opener.open.call_args.args[0]
            self.assertEqual(request.method, "POST")
            self.assertIn("sintético", request.data.decode())
            response.read.return_value = b'x' * (2 * 1024 * 1024 + 1)
            with self.assertRaises(ProviderError):
                http_json("http://127.0.0.1:11434", {}, {}, 2)
