# Current-turn scope correction

## Reproduction and root cause

The failure was reproduced with actual local qwen3:4b-instruct before editing:
a catalog query returned two synthetic products, then the same Agent answered
"The capital of France is Paris" and generated a Python bubble-sort function.
Both unrelated turns used zero business tools.

Agent previously treated any successful tool result anywhere in retained history
as evidence permitting a later text-only answer. The system prompt named a music
store but did not explicitly restrict subsequent topics. Fact evidence and
permission to answer a new topic were conflated.

## Minimal correction

The same configured LLM makes one isolated structured scope decision before each
non-greeting business turn. The scope prompt defines shop support generally,
including instrument features/selection/comparisons, catalog, pricing, policies,
store information, and order inquiries. There is no list of hardcoded geography
or programming test questions, new provider, model, framework, or routing service.

Python validates exactly one check_shop_scope call with decision shop/outside/
uncertain and language pt/en. Only shop continues. Missing, malformed, extra, or
multiple decisions fail closed to clarification. Network errors do not bypass
scope. A current-question language hint prevents the model from reusing an old
conversation language for a Portuguese/English redirect.

Scope receives only the current question and two bounded previous customer
questions for genuine references. It receives no historical tool results or
customer/order DTOs. Prior successful tools never authorize the new turn. Scope
is not authentication: even an order number without identity proof is a shop
question; the existing Python service still decides ownership and returns uniform
denials. Scope cannot bind or change identity.

Rejected/uncertain questions and classifier replies are not added to business
memory. A valid follow-up can resume the earlier store conversation. The web
session displays the safe redirect as a normal answer. No desktop layout,
window behavior, data fixtures, pricing, policy, or authorization logic changed.
Gemini's original privacy projection happens before scope; raw unsupported input
is never forwarded to that provider.

The scope decision adds one model request. The original four business-request
iterations and six business-tool calls remain intact: at most five model requests
per turn by default. Preflight testing caught the regression from deducting scope
from those four iterations: a real pricing lookup needed get_product, a rejected
ungrounded draft, get_price_quote, then the guarded final answer. Keeping the
existing bounded recovery allowance restored that valid path. No automatic
retry, paid fallback, or broader tool budget was added.

## Verification

Full suite with live Ollama enabled: **162 tests, 161 passed, 1 skipped**, no
failures/errors, 57.181 seconds. The skip is Gemini's absent free-tier credentials.
All five live Ollama tests passed: original pricing/catalog/return checks and two
new scope tests. Ten new mocked scope tests cover initial/after-lookup refusals,
programming/mixed requests, resuming valid follow-ups, legitimate requests,
malformed decisions, network failure, language, bounds, Gemini projection, and
web redirect handling. Existing business tests stub the scope decision to isolate
their original business/transport assertions; they are not advertised as live
scope classification. Dedicated tests exercise the real approval gate.

Separate genuine synthetic-only conversations verified English and Portuguese
redirects, a full two-product catalog, PIX price 90.09, a contextual discount
follow-up, policy retrieval, and the authorized historical order total 99.00.
Eight actual scope probes accepted instrument materials, MIDI setup, comparisons,
an unfamiliar model name, store hours, warranties and order questions, and
rejected a mixed shop-plus-unrelated-code request. Preflight exposed an order
false refusal; clarifying scope versus ownership corrected it before final tests.
No existing transcript was edited to hide a failed or stylistically imperfect run.

Run all checks explicitly:

```powershell
$env:EMPORIO_RUN_LIVE = "1"
$env:OLLAMA_MODEL = "qwen3:4b-instruct"
python -m unittest discover -s tests -v
```

## Limits and submission status

Scope is a bounded model decision, not a formal proof against every ambiguous
request or adversarial prompt. Misclassification remains possible; invalid or
uncertain output asks for clarification. One extra inference adds latency and
free-tier quota usage. Broader multilingual evaluation is preferable to adding
brittle phrase exceptions. General generated policy prose retains its existing
limitations; deterministic factual guards remain unchanged.

The existing sixteen-commit history is preserved. Original challenge requirements
were checked locally; README now acknowledges the existing remote and earlier
pushes, the reviewed brief, and possible additional PDF/Forms delivery. The public
GitHub accessibility, final publish authorization, exact deadline and recruiting
email/Forms requirements still need confirmation. No push, visibility change or
submission was performed for this correction. Restart old application processes
to load the new scope guard.
