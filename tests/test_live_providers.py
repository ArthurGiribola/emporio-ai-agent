"""Opt-in genuine model smoke tests. Only built-in synthetic fixtures are used."""

import os
import socket
import unittest
from urllib.parse import urlsplit

from app.agent import Agent
from app.providers import ProviderConfig, create_provider
from app.synthetic import QUESTIONS, SyntheticTools


@unittest.skipUnless(os.environ.get("EMPORIO_RUN_LIVE") == "1", "Live model tests disabled; set EMPORIO_RUN_LIVE=1 explicitly")
class LiveProviderTests(unittest.TestCase):
    def check_synthetic_price(self, config):
        with SyntheticTools() as tools:
            result = Agent(create_provider(config), tools).run(QUESTIONS["price"])
        self.assertEqual(result.status, "answered", result.text)
        self.assertIn("get_price_quote", result.tools_called)

    def test_gemini_free_tier_synthetic_function_call(self):
        if not os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_FREE_TIER_CONFIRMED") != "1":
            self.skipTest("Gemini key/Free Tier confirmation not configured locally")
        env = dict(os.environ, LLM_PROVIDER="gemini", LLM_MODEL="gemini-3.1-flash-lite")
        self.check_synthetic_price(ProviderConfig.from_environment(env))

    def test_ollama_local_synthetic_function_call(self):
        env = dict(os.environ, LLM_PROVIDER="ollama", LLM_MODEL=os.environ.get("OLLAMA_MODEL", "qwen3:4b"))
        config = ProviderConfig.from_environment(env)
        url = urlsplit(config.base_url)
        try:
            with socket.create_connection((url.hostname, url.port), timeout=1):
                pass
        except OSError:
            self.skipTest("Local Ollama server unavailable")
        self.check_synthetic_price(config)
