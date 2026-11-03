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
from app.diagnostics import developer_observer


@dataclass(frozen=True)
class ChatAnswer:
    text: str
    references: tuple[str, ...] = ()
    error: bool = False
    catalog: CatalogView | None = None


class ChatSession:
    def __init__(self, *, provider_factory=create_provider, environment=None):
        env = os.environ if environment is None else environment
        self._diagnostics = developer_observer(env.get('EMPORIO_DIAGNOSTICS') == '1')
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
            self._agent = Agent(provider_factory(config), self._tools, observer=self._observe, order_id=self._order_id)
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
        self._diagnostics(event)
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
        except Exception as error:
            # Never render an exception, file path, response body, or traceback.
            self._diagnostics({'event':'unexpected_failure','phase':'orchestration', 'exception_type':type(error).__name__})
            return ChatAnswer('I could not complete this lookup. Please retry; your conversation was kept.' if english_question(question) else
                              'Não consegui concluir esta consulta. Tente novamente; sua conversa foi mantida.', error=True)
        if result.status in {"out_of_scope", "scope_uncertain"}:
            return ChatAnswer(result.text)
        if result.status != "answered":
            return ChatAnswer(result.text, error=True)
        if result.catalog is not None:
            shown = len(result.catalog.entries)
            if shown == 0:
                return ChatAnswer(result.text, tuple(self._references), catalog=result.catalog)
            # Total found and the number shown are different facts; never conflate them.
            total = result.catalog.total_matches
            if english_question(question):
                source = 'demonstration catalog' if result.catalog.synthetic else 'catalog'
                found = (f'I found {total} products in our {source}' if shown == total else
                         f'I found {total} products in our {source}; showing {shown} of {total}')
                text = found + '. Browse the pages or select an item for details.'
                if result.catalog_prompt:
                    text = found + '. ' + result.catalog_prompt
            else:
                source = 'catálogo de demonstração' if result.catalog.synthetic else 'catálogo'
                found = (f'Encontrei {total} produtos no {source}' if shown == total else
                         f'Encontrei {total} produtos no {source}; mostrando {shown} de {total}')
                text = found + '. Você pode navegar pelas páginas ou selecionar um item para ver os detalhes.'
                if result.catalog_prompt:
                    text = found + '. ' + result.catalog_prompt
            return ChatAnswer(text, tuple(self._references), catalog=result.catalog)
        return ChatAnswer(result.text, tuple(self._references))

    def order_details(self):
        """Startup-selected order; ownership stays inside the bound service."""
        try:
            return self._tools._orders.lookup_order(self._order_id)
        except Exception:
            return OrderLookupResult("error", None, "Order lookup could not be completed.")

    def select_product(self, product_id):
        self._agent.focus_product(product_id)

    def reset(self):
        self._agent.reset()
        self._references.clear()

    def close(self):
        self._data_context.__exit__(None, None, None)
