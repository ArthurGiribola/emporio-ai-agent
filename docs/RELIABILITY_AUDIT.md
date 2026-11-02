# Conversational reliability audit

Date: 2026-11-02. Local model: `qwen3:4b-instruct` through Ollama. The approved monochrome interface is preserved. The separate color preview was suspended and saved outside Git. No repository was pushed or submitted.

## Confirmed causes

| Defect | Evidence and correction |
| --- | --- |
| Visible history disappeared | Streamlit sliced the transcript to its last eight messages. A failing regression retained only eight of twenty. The slice is removed; internal navigation never clears the transcript. Only explicit Reset clears the active session. |
| Wrong catalog reference | Plural references bypassed the positional map. In an actual LOCAL run, item 20 was looked up as source ID 124 rather than its correct source ID 113. Singular/plural positions now resolve before tools; explicit source IDs remain distinct. Ambiguous/out-of-range positions ask for clarification. |
| Only one of several products answered | The stock formatter returned inside a reversed results loop. It now renders every verified requested product. Source IDs outside the resolved request are rejected, and every requested product must have evidence before completion. |
| Invented explanations and quantities | A successful prior tool call made `evidence` true for later drafts without fresh evidence. Actual follow-ups claimed IDs had been verified and invented an explanation of an incorrect lookup. Critical facts now use deterministic services; lookup failures and unqueried absence claims cannot become assertions that products do not exist. |
| Follow-up scope/context loss | The scope checker received only two questions, without the answers or the last failure. It now receives bounded verified answer context. Narrow history/failure questions get factual local explanations; unrelated requests still cannot obtain general-purpose answers. |
| Model memory and visual selection | Four model exchanges and UI-only selection were insufficient for follow-ups. Model memory is separate from the complete transcript: up to eight exchanges/20,000 serialized characters, intact call/result pairs, explicitly partial catalog excerpts, a durable latest-list map and up to six recently discussed product IDs. Visual selection validates the product against the shared catalog before binding product context. |
| Silent PIX carry-over | A native desktop follow-up and actual trace showed the model sending `payment_method: pix` for a different selected product without PIX in the question. Python now defaults that request to the normal promotional price. The same actual sequence returned R$ 250.00 without PIX and R$ 237.50 only when PIX was requested. Decimal calculations and non-stacking rules are unchanged. |
| Generic English errors | The web adapter collapsed distinct statuses into one English string. Typed provider/transport/tool/limit reasons now produce actionable customer messages without requesting a conversation reset. Malformed/incomplete business output gets at most one recovery attempt inside the existing four-request budget. No timeout or output limit was increased. |
| Order mismatch/omission | Natural `meu pedido` now binds the same startup-selected order as the screen; ownership still belongs to OrderService. Chat includes the same recorded item names and quantities, historical total and missing-field information. Authorized item lines are complete within the existing 12K result ceiling. No contact data, notes, identity setter or mutation tool is introduced. |

The exact pasted original conversation could not be replayed with its missing earlier state. The defects above were independently reproduced using actual tool arguments/results and deterministic regressions; the report does not claim every original word was reproduced.

## Verification and evidence

[Actual synthetic Ollama conversations](RELIABILITY_CONVERSATIONS.json) are genuine executions, not mocked responses. LOCAL policy/catalog traces, full developer diagnostics and native screenshots are kept outside the public repository. Mocked provider tests and Streamlit AppTest are explicitly separate from actual LLM runs.

The evaluated scenarios cover catalog references (including items 1, 20 and 62), stock and prices, PIX/non-stacking, comparisons and quantity clarification, purchase interest without transactions, a five-day online return and source follow-ups, unrelated-code refusal followed by a legitimate question, provider/tool errors and recovery, and protected orders. CLI runs in both synthetic and LOCAL modes exited successfully. A controlled real loopback network fault produced a Portuguese timeout explanation; the same Agent subsequently resumed genuine Ollama queries without resetting identity or context. This was a controlled network fault, not a claim of an actual Ollama outage.

The final complete suite ran 220 tests in 65.787 seconds: 219 passed and one Gemini test was skipped because a key/free-tier confirmation was not configured. Five test methods executed actual Ollama requests, alongside deterministic, mocked-provider, Streamlit AppTest and private-file checks. A separate actual-model audit executed 29 turns: 27 answered, one expected unrelated-programming refusal and one expected nonexistent-product error. Twenty synthetic turns from that audit are published verbatim in the linked JSON; LOCAL traces remain private.

The actual Windows pywebview/Streamlit window was exercised with Ollama in DEMO mode: catalog discussion, Nylon details, another catalog visit, Aço selection, return to chat, pronoun-based price, My Order and back, natural-language order contents, a history question and a reference to the other instrument. The screen and chat both returned one Nylon, recorded total R$ 99.00 and unknown tracking/delivery dates. Aço cost R$ 250.00; the other instrument resolved to Nylon with three recorded units. The original chat messages remained present beyond the old eight-message cutoff. The final desktop check also refused an English programming request before accepting a Portuguese stock question.

This native test exposed one additional scope-context failure after intervening order/history topics. The scope check now receives the validated recently discussed instrument names, rather than relying only on the last two answers. The exact failing desktop follow-up was repeated successfully after this focused correction. Screenshots and full native accessibility transcripts are retained outside Git; the UI, themes and desktop dimensions were not redesigned.

## Diagnostics and boundaries

`EMPORIO_DIAGNOSTICS=1` enables structured events on local stderr for CLI/desktop. Only event types, known reason/status codes, counts and selected exception class names are included. Questions, raw model/tool bodies, argument values, customer IDs, credentials and policy text are excluded. Detailed raw traces used for this audit remain outside Git.

The visible transcript is in RAM for the active Streamlit session; reopening the application or losing the session is not persistent chat storage. The LLM receives bounded context rather than the entire transcript. Ambiguous references or unavailable earlier details require clarification. Payments must be explicit for payment-specific discounts. Quantity discussion does not reserve stock or create orders. Data is recorded source evidence, not live inventory/shipping events. Demo identity binding is not production authentication.

PASS on evaluated scenarios is not a guarantee that a small local model never times out, emits malformed output, or needs clarification. Those failures must remain honest, bounded and recoverable. No universal submission-ready certification is implied.
