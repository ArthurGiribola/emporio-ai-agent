# No-paid-API provider strategy

Official documentation checked November 1, 2026. Recheck before submission:
models, eligibility, and quotas can change.

| Provider | Model | Function calling | Access |
| --- | --- | --- | --- |
| Gemini Developer API | gemini-3.1-flash-lite | Supported; stable | Documented free input/output tier; project quotas apply |
| Ollama native local API | qwen3:4b suggested; configurable | Supported; installed model checked | Local inference; needs weights and adequate hardware |

Gemini is the default. A verified-model allowlist rejects unverified or paid
models. There is no OpenAI SDK/key, paid fallback, automatic retry, billing
activation, model download, or automatic provider switch.

Free Tier belongs to the API key's project, not its model name. Use an active
Free Tier project without linked billing, and check quota in Google AI Studio.
GEMINI_FREE_TIER_CONFIRMED=1 is an operator attestation, not technical billing
verification: the inference key cannot tell this app whether billing is enabled.
Never enable billing to bypass quota failures. HTTP 429 stops; choose Ollama
manually if needed. Brazil is listed as supported; account requirements apply.

Free-tier content may be used to improve Google's products. The application
cloud path accepts only approved packaged synthetic fixtures and filtered
synthetic intent vocabulary; arbitrary original text is not forwarded. Actual customer/order records and the restricted manual stay local.
This avoids relying on imperfect PII masking or model instructions.

## Native contracts and boundaries

Adapters use standard-library HTTP/JSON with no new dependency. Gemini uses
models/{model}:generateContent, parametersJsonSchema declarations, and structured
functionResponse parts. Native model parts, including thought signatures, are
replayed unchanged. store=false does not override free-tier data-use terms.

Ollama checks /api/show for tools capability and uses /api/chat, stream=false.
Native assistant tool calls/thinking are preserved. Only explicit HTTP loopback
IP/port endpoints are accepted; cloud model names and remote-model metadata are
rejected. Redirects and ambient proxies are disabled. Start the trusted server
with OLLAMA_NO_CLOUD=1. A loopback URL cannot prove what another server process
does. Model weights must already be installed; the app never pulls them.

Timeout, response size, and output tokens are bounded. Failures are sanitized.
Keys are headers, excluded from config representations and errors. Requests and
raw response bodies are not logged. Adapters are trusted Python APIs, never
functions available for a model to invoke.

## Verification limits

The initial provider work had no configured Gemini key or local Ollama runtime.
Local qwen3:4b-instruct is now available: genuine catalog/return correctness
regressions and the synthetic pricing smoke check have passed. Gemini live
project eligibility remains unverified without its key/free-tier confirmation.
Cloud checks remain synthetic-only. Authorized source-data checks run only on
local Ollama, explicitly opt-in, with honest skips when prerequisites are absent.

## Primary sources

- [Gemini model](https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite)
- [Pricing and data use](https://ai.google.dev/gemini-api/docs/pricing)
- [Billing and Free Tier](https://ai.google.dev/gemini-api/docs/billing)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Available regions](https://ai.google.dev/gemini-api/docs/available-regions)
- [Native API schema](https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta)
- [Function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Ollama tools](https://docs.ollama.com/capabilities/tool-calling)
- [Ollama chat](https://docs.ollama.com/api/chat)
- [Ollama capabilities](https://docs.ollama.com/api-reference/show-model-details)
- [Local-only server](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)
- [Local model](https://ollama.com/library/qwen3:4b)

## Interactive scope

The CLI supports multi-turn conversations. Ollama can use arbitrary questions
and authorized local store files. Gemini only receives synthetic fixtures and
locally projected demo vocabulary. The optional fixed-scenario runner is a smoke
test, not the conversational agent. Setup is in the README.
