"""Session-scoped synthetic demo; no private paths, cloud provider, or identity UI."""

import os
from dataclasses import dataclass

from app.agent import Agent
from app.orders import OrderLookupResult
from app.providers import ProviderConfig, create_provider
from app.synthetic import SyntheticTools


@dataclass(frozen=True)
class ChatAnswer:
    text: str
    references: tuple[str, ...] = ()
    error: bool = False


class ChatSession:
    def __init__(self, *, provider_factory=create_provider, environment=None):
        env = os.environ if environment is None else environment
        # Deliberately independent of the CLI's Gemini default and API keys.
        config = ProviderConfig(provider="ollama", model=env.get("OLLAMA_MODEL", "qwen3:4b"),
                                base_url=env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                                timeout_seconds=120, max_output_tokens=2048)
        self._references = []
        self._tools = SyntheticTools()
        try:
            self._agent = Agent(provider_factory(config), self._tools, observer=self._observe)
        except Exception:
            self._tools.close()
            raise

    def _observe(self, event):
        # Keep only validated citation coordinates, never raw model/tool diagnostics.
        if event.get("event") != "tool_result" or event.get("name") != "search_policies":
            return
        result = event.get("result", {})
        if result.get("status") != "ok":
            return
        for ref in result.get("data", {}).get("references", []):
            section, pages = ref.get("section"), ref.get("pages", [])
            if (isinstance(section, str) and len(section) <= 16
                    and all(c in "0123456789." for c in section)
                    and isinstance(pages, (list, tuple)) and pages
                    and all(type(p) is int and p > 0 for p in pages)):
                label = f"Synthetic policy · Section {section} · page(s) {', '.join(map(str, pages))}"
                if label not in self._references:
                    self._references.append(label)

    def ask(self, question):
        self._references.clear()
        try:
            result = self._agent.run(question)
        except Exception:
            # Never render an exception, file path, response body, or traceback.
            return ChatAnswer("This turn could not be completed. Please reset the conversation and try again.", error=True)
        if result.status != "answered":
            text = ("The local model could not complete this turn. Check that Ollama is running and the model is installed, then try again."
                    if result.status == "provider_error" else
                    "I could not verify an answer. Try a shorter, more specific question, or reset the conversation.")
            return ChatAnswer(text, error=True)
        return ChatAnswer(result.text, tuple(self._references))

    def order_details(self):
        """Fixed demo order; ownership stays inside the bound Python service."""
        try:
            return self._tools._orders.lookup_order(1)
        except Exception:
            return OrderLookupResult("error", None, "Order lookup could not be completed.")

    def reset(self):
        self._agent.reset()
        self._references.clear()

    def close(self):
        self._tools.close()
