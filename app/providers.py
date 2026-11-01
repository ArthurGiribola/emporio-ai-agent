"""Small native REST adapters. No paid provider dependency or automatic fallback."""

import copy
import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
# Documented free-tier/function-calling combination verified on 2026-11-01.
FREE_TIER_MODELS = frozenset({DEFAULT_GEMINI_MODEL})
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ProviderError(RuntimeError):
    """Sanitized operational failure; never includes headers, keys, or response bodies."""


class ConfigurationError(ValueError):
    """Provider configuration is incomplete or outside the no-paid/local policy."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "gemini"
    model: str = DEFAULT_GEMINI_MODEL
    api_key: str = field(default="", repr=False)
    free_tier_confirmed: bool = False
    base_url: str = "http://127.0.0.1:11434"
    timeout_seconds: int = 30
    max_output_tokens: int = 1024

    def __post_init__(self):
        if self.provider not in {"gemini", "ollama"}:
            raise ConfigurationError("Supported providers are gemini and ollama")
        if type(self.timeout_seconds) is not int or not 1 <= self.timeout_seconds <= 120:
            raise ConfigurationError("Provider timeout must be between 1 and 120 seconds")
        if type(self.max_output_tokens) is not int or not 64 <= self.max_output_tokens <= 4096:
            raise ConfigurationError("Output limit must be between 64 and 4096 tokens")
        if self.provider == "gemini":
            if self.model not in FREE_TIER_MODELS:
                raise ConfigurationError("Gemini model has not been verified for this free-tier integration")
            if self.free_tier_confirmed is not True:
                raise ConfigurationError("Confirm a Free Tier project without billing using GEMINI_FREE_TIER_CONFIRMED=1")
            if not isinstance(self.api_key, str) or not self.api_key.strip():
                raise ConfigurationError("Set GEMINI_API_KEY locally; never paste or commit it")
        else:
            try:
                url = urlsplit(self.base_url)
                valid = (url.scheme == "http" and url.hostname in {"127.0.0.1", "::1"}
                         and url.port is not None and not url.username and not url.password
                         and url.path in {"", "/"} and not url.query and not url.fragment)
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise ConfigurationError("Ollama endpoint must be an explicit HTTP loopback address and port")
            if not isinstance(self.model, str) or not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,100}", self.model) or "cloud" in self.model.casefold():
                raise ConfigurationError("Use a locally installed Ollama model, not a cloud model")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None):
        env = os.environ if environment is None else environment
        provider = env.get("LLM_PROVIDER", "gemini")
        return cls(provider=provider,
                   model=env.get("LLM_MODEL") or (DEFAULT_GEMINI_MODEL if provider == "gemini" else "qwen3:4b"),
                   api_key=env.get("GEMINI_API_KEY", ""),
                   free_tier_confirmed=env.get("GEMINI_FREE_TIER_CONFIRMED") == "1",
                   base_url=env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    """Bounded JSON POST, with no redirects, ambient proxies, retries, or logging."""
    try:
        request = Request(url, data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
                          headers={"Content-Type": "application/json", **headers}, method="POST")
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError("Provider response exceeded the size limit")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ProviderError("Provider returned an invalid response")
        return result
    except HTTPError as error:
        code = error.code
        error.close()
        if code == 429:
            raise ProviderError("Provider quota/rate limit reached; no retry or paid fallback was attempted") from None
        raise ProviderError(f"Provider request failed (HTTP {code}); check configuration or availability") from None
    except (URLError, TimeoutError, OSError, UnicodeError, ValueError):
        raise ProviderError("Provider connection or JSON response failed") from None


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    call_id: str = ""


@dataclass(frozen=True)
class ProviderReply:
    text: str
    calls: tuple[ToolCall, ...]
    native: dict = field(repr=False)


def _calls(values: list, *, gemini: bool) -> tuple[ToolCall, ...]:
    result = []
    if not isinstance(values, list) or len(values) > 8:
        raise ProviderError("Invalid or excessive provider tool calls")
    for value in values:
        function = value if gemini else value.get("function", {}) if isinstance(value, dict) else {}
        if (not isinstance(function, dict) or not isinstance(function.get("name"), str)
                or not isinstance(function.get("args" if gemini else "arguments", {}), dict)):
            raise ProviderError("Invalid provider tool call")
        call_id = function.get("id", "") if gemini else str(function.get("index", ""))
        if not isinstance(call_id, str) or len(call_id) > 200:
            raise ProviderError("Invalid provider call identifier")
        result.append(ToolCall(function["name"], function.get("args" if gemini else "arguments", {}), call_id))
    return tuple(result)


class GeminiProvider:
    external = True

    def __init__(self, config: ProviderConfig, transport: Callable = http_json):
        if config.provider != "gemini":
            raise ConfigurationError("Expected Gemini configuration")
        self.config, self._transport = config, transport

    def complete(self, history: list[dict], tools: list[dict], system: str) -> ProviderReply:
        contents = []
        for message in history:
            if message["role"] == "assistant":
                # Preserve all parts, including thought signatures, exactly as returned.
                contents.append(copy.deepcopy(message["native"]))
            elif message["role"] == "tool":
                response = {"name": message["name"], "response": message["result"]}
                if message["call_id"]:
                    response["id"] = message["call_id"]
                part = {"functionResponse": response}
                if contents and contents[-1].get("role") == "user" and "functionResponse" in contents[-1]["parts"][0]:
                    contents[-1]["parts"].append(part)
                else:
                    contents.append({"role": "user", "parts": [part]})
            else:
                contents.append({"role": "user", "parts": [{"text": message["content"]}]})
        declarations = [{"name": tool["name"], "description": tool["description"],
                         "parametersJsonSchema": tool["parameters"]} for tool in tools]
        payload = {"contents": contents, "systemInstruction": {"parts": [{"text": system}]},
                   "tools": [{"functionDeclarations": declarations}],
                   "generationConfig": {"maxOutputTokens": self.config.max_output_tokens},
                   "store": False}
        response = self._transport(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent",
            payload, {"x-goog-api-key": self.config.api_key}, self.config.timeout_seconds)
        try:
            candidate = response["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ProviderError("Provider response was blocked or incomplete")
            native = candidate["content"]
            parts = native["parts"]
            if native.get("role") != "model" or not isinstance(parts, list) or not all(isinstance(p, dict) for p in parts):
                raise ProviderError("Invalid provider content")
            text = "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))
            calls = _calls([p["functionCall"] for p in parts if "functionCall" in p], gemini=True)
            return ProviderReply(text, calls, copy.deepcopy(native))
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("Provider returned an invalid or blocked response") from None


class OllamaProvider:
    external = False

    def __init__(self, config: ProviderConfig, transport: Callable = http_json):
        if config.provider != "ollama":
            raise ConfigurationError("Expected Ollama configuration")
        self.config, self._transport = config, transport
        self._checked = False

    def complete(self, history: list[dict], tools: list[dict], system: str) -> ProviderReply:
        base = self.config.base_url.rstrip("/")
        if not self._checked:
            info = self._transport(base + "/api/show", {"model": self.config.model}, {}, self.config.timeout_seconds)
            if (not isinstance(info, dict) or not isinstance(info.get("capabilities"), list)
                    or "tools" not in info["capabilities"] or info.get("remote_host")
                    or info.get("remote_model")):
                raise ProviderError("Ollama requires an installed local model with tools capability")
            self._checked = True
        messages = [{"role": "system", "content": system}]
        for message in history:
            if message["role"] == "assistant":
                messages.append(copy.deepcopy(message["native"]))
            elif message["role"] == "tool":
                messages.append({"role": "tool", "tool_name": message["name"],
                                 "content": json.dumps(message["result"], ensure_ascii=False, allow_nan=False)})
            else:
                messages.append({"role": "user", "content": message["content"]})
        payload = {"model": self.config.model, "messages": messages, "stream": False,
                   "tools": [{"type": "function", "function": tool} for tool in tools],
                   "options": {"num_predict": self.config.max_output_tokens}}
        response = self._transport(base + "/api/chat", payload, {}, self.config.timeout_seconds)
        try:
            native = response["message"]
            if not response.get("done") or response.get("done_reason") == "length" or native.get("role") != "assistant":
                raise ProviderError("Ollama response was incomplete")
            text = native.get("content", "")
            if not isinstance(text, str):
                raise ProviderError("Invalid Ollama content")
            return ProviderReply(text, _calls(native.get("tool_calls", []), gemini=False), copy.deepcopy(native))
        except (KeyError, TypeError, AttributeError):
            raise ProviderError("Ollama returned an invalid response") from None


def create_provider(config: ProviderConfig, transport: Callable = http_json):
    return GeminiProvider(config, transport) if config.provider == "gemini" else OllamaProvider(config, transport)
