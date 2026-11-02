# Customer-facing response refinement

The shared agent now asks for a practical answer first, short paragraphs, natural
Brazilian Portuguese or English, and helpful follow-ups only when needed. It
avoids internal field/tool names, repetitive freshness disclaimers and scripted
closings. A trusted data-mode label identifies demonstrations without labeling
real local records as synthetic.

Deterministic catalog, quote and order renderers remain responsible for the same
verified facts. Product lists have blank lines around them, accurate complete or
partial counts, and the existing price ordering. Quotes explain promotions and
the non-stacking PIX restriction in everyday language. Orders retain their
historical totals and explicit missing tracking/dates/item prices. Return-window
answers lead with timing, keep conditions and refund evidence, and do not imply
that a return has been approved. UI source captions are combined into one note.
No product response, price or policy duration was hardcoded into application copy.

## Findings during real verification

With actual local `qwen3:4b-instruct`, an English warranty question after Portuguese
turns could receive a Portuguese answer. The already-validated current-turn
language is now repeated in the system prompt and beside the current question in
a temporary provider-history copy. Stored customer messages, scope input, tool
arguments, identity and provider limits remain unchanged.

A native desktop preflight also generated an unsupported warranty exclusion after
a successful catalog turn. The existing fresh-evidence requirement now includes
explicit Portuguese/English policy questions. Synthetic placeholder sections
contain no terms to paraphrase, so the presentation layer gives a concise,
localized explanation of missing information with actual retrieved references.
This does not turn missing warranty terms into a claim that no warranty exists.
The original scope, privacy, authorization and arithmetic controls remain intact.

## Verification

Automated regressions cover bilingual sorted lists and spacing, partial counts,
quality warnings, exact prices, unavailable products, PIX/promotion restrictions,
historical totals, missing order data, five-day/seven-day return wording,
current-language prompt binding, and catalog-to-warranty grounding. Existing
tests continue covering cross-customer denials, cloud privacy, scope and original
data correctness. These unit tests use synthetic services/mocked providers and
are not presented as live conversation transcripts.

Final complete suite with live Ollama enabled: **170 tests in 65.523 seconds,
169 passed, 1 skipped**, no failures/errors. All five real Ollama test methods
passed, including the original twelve-product catalog and five-day online-return
checks and the scope checks. The sole skip was Gemini's missing credentials and
free-tier confirmation. Seven new response-quality tests were added.

Separate actual synthetic-only Ollama conversations were executed through:

- CLI: Portuguese full catalog, English PIX quote, Portuguese return uncertainty,
  English warranty clarification with references, unrelated programming refusal,
  and Portuguese authorized order details. Exit code 0.
- Streamlit browser: Portuguese full catalog, English warranty clarification with
  references, then English PIX quote at 90.09.
- Windows mini-chat: Portuguese full catalog followed by the English warranty
  question that exposed the preflight failure. The corrected run explains missing
  demonstration terms and cites retrieved sections instead of inventing coverage.

Raw observations, screenshots and failed preflight captures are retained locally
outside the repository. No private source documents or customer data are included
in those demonstration artifacts. No interface redesign or new dependency was
introduced; old running processes must be restarted to load the changes.

## Limits

Free-form comparisons and non-templated policy explanations still depend on the
configured model; prompts cannot prove perfect tone, language or grounding for
every question. Language switching improved in the checked conversations, not a
guarantee for every ambiguous multilingual request. The synthetic policy is
intentionally incomplete and must not be treated as real store terms. Concision
does not remove explicit uncertainties or restrictions. No real stock, shipment,
refund or return action is implied by these read-only answers.
