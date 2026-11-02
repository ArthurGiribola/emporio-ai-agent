"""Startup-bound DEMO/LOCAL sessions; no cloud provider or identity UI."""

import os
from dataclasses import dataclass
from pathlib import Path

from app.agent import Agent
from app.data_session import open_tools
from app.orders import OrderLookupResult
from app.providers import ProviderConfig, create_provider
from app.catalog_view import CatalogView
from app.grounding import english_question


@dataclass(frozen=True)
class ChatAnswer:
    text: str
    references: tuple[str, ...] = ()
    error: bool = False
    catalog: CatalogView | None = None


class ChatSession:
    def __init__(self, *, provider_factory=create_provider, environment=None):
        env = os.environ if environment is None else environment
        # Deliberately independent of the CLI's Gemini default and API keys.
        config = ProviderConfig(provider="ollama", model=env.get("OLLAMA_MODEL", "qwen3:4b"),
                                base_url=env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                                timeout_seconds=120, max_output_tokens=2048)
        self._references = []
        self._mode = env.get('EMPORIO_DATA_MODE', 'demo').lower()
        if self._mode not in {'demo', 'local'}:
            raise ValueError('EMPORIO_DATA_MODE must be demo or local')
        enabled = env.get('EMPORIO_ENABLE_DEMO_IDENTITY', '0')
        if enabled not in {'0', '1'}:
            raise ValueError('Demo identity opt-in must be 0 or 1')
        self._identity_enabled = self._mode == 'demo' or enabled == '1'
        identity = env.get('EMPORIO_DEMO_CUSTOMER_ID')
        self._order_id = int(env.get('EMPORIO_ORDER_ID', '1'))
        if not 1 <= self._order_id < 10**12:
            raise ValueError('Invalid startup order')
        if self._mode == 'demo' and any(env.get(key) for key in (
                'EMPORIO_DATA_DIR', 'EMPORIO_POLICY_PATH', 'EMPORIO_DEMO_CUSTOMER_ID', 'EMPORIO_ORDER_ID')):
            raise ValueError('DEMO uses fixed synthetic resources and order only')
        data_dir = env.get('EMPORIO_DATA_DIR', str(Path(__file__).resolve().parents[1] / 'data')) if self._mode == 'local' else Path('data')
        self._data_context = open_tools('synthetic' if self._mode == 'demo' else 'local', data_dir=data_dir,
            policy_path=env.get('EMPORIO_POLICY_PATH'), enable_demo_identity=enabled == '1',
            demo_customer_id=int(identity) if identity is not None else None)
        self._tools = self._data_context.__enter__()
        try:
            self._agent = Agent(provider_factory(config), self._tools, observer=self._observe)
        except Exception:
            self._data_context.__exit__(None, None, None)
            raise

    @property
    def mode(self):
        return self._mode.upper()

    @property
    def mode_caption(self):
        if self._mode == 'demo':
            return 'DEMO · Dados sintéticos · Ollama local · Identidade fixa · Somente leitura'
        identity = 'Identidade de demonstração fixa' if self._identity_enabled else 'Pedidos sem identificação'
        return f'LOCAL · Dados originais · Ollama local · {identity} · Somente leitura'

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
                source = 'Synthetic policy' if self._mode == 'demo' else 'Store policy'
                label = f"{source} · Section {section} · page(s) {', '.join(map(str, pages))}"
                if label not in self._references:
                    self._references.append(label)

    def ask(self, question):
        self._references.clear()
        try:
            result = self._agent.run(question)
        except Exception:
            # Never render an exception, file path, response body, or traceback.
            return ChatAnswer("This turn could not be completed. Please reset the conversation and try again.", error=True)
        if result.status in {"out_of_scope", "scope_uncertain"}:
            return ChatAnswer(result.text)
        if result.status != "answered":
            text = ("The local model could not complete this turn. Check that Ollama is running and the model is installed, then try again."
                    if result.status == "provider_error" else
                    "I could not verify an answer. Try a shorter, more specific question, or reset the conversation.")
            return ChatAnswer(text, error=True)
        if result.catalog is not None:
            count = len(result.catalog.entries)
            if count == 0:
                return ChatAnswer(result.text, tuple(self._references), catalog=result.catalog)
            if english_question(question):
                source = 'demonstration catalog' if result.catalog.synthetic else 'catalog'
                text = f'I found {count} products in our {source}. Browse the pages or select an item for details.'
            else:
                source = 'catálogo de demonstração' if result.catalog.synthetic else 'catálogo'
                text = f'Encontrei {count} produtos no {source}. Você pode navegar pelas páginas ou selecionar um item para ver os detalhes.'
            return ChatAnswer(text, tuple(self._references), catalog=result.catalog)
        return ChatAnswer(result.text, tuple(self._references))

    def order_details(self):
        """Startup-selected order; ownership stays inside the bound service."""
        try:
            return self._tools._orders.lookup_order(self._order_id)
        except Exception:
            return OrderLookupResult("error", None, "Order lookup could not be completed.")

    def reset(self):
        self._agent.reset()
        self._references.clear()

    def close(self):
        self._data_context.__exit__(None, None, None)
