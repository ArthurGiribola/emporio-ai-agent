# Actual DEMO conversations

These five conversations use local Ollama `qwen3:4b-instruct` and only the
approved synthetic DEMO fixtures. Four examples remain from the original
November 3 capture. The return-policy example was recaptured after the focused
routing fix; the customer questions, assistant responses, synthetic evidence,
and tool names are actual live outputs, not mocked tests. The other four
conversations were left unchanged.

This is an evidence set, not a guarantee of reliability. The current capture
still records the catalog/PIX follow-up failure. The return-policy example now
retrieves the synthetic 11-day rule and correctly evaluates its five-day
follow-up. This is a fictitious DEMO rule and is not the supplied LOCAL policy.
The previous erroneous order lookup and failed follow-up are preserved verbatim
under [`archive/2026-11-03-pre-fix`](archive/2026-11-03-pre-fix/03-return-policy-routing.md).

| Conversation | Observed behavior |
| --- | --- |
| [Catalog, budget, and PIX](01-catalog-budget-pix.md) | Catalog result is correct; the next-turn “cheapest/PIX” question fails to resolve its reference. |
| [Multi-turn purchase inquiry](02-purchase-multiturn.md) | Stock and PIX facts are grounded; requesting 10 when only 3 are recorded is refused as a completed purchase. |
| [Return policy and elapsed-day follow-up](03-return-policy-routing.md) | Real Ollama now selects policy retrieval and correctly assesses five days under the synthetic rule; the earlier failure is archived. |
| [Authorized order](04-authorized-order.md) | Authorized synthetic order is read-only; missing tracking/delivery fields remain unknown. |
| [Store information and scope](05-store-information-and-scope.md) | Missing opening-hour evidence is disclosed; an unrelated math request is redirected. |

`live-conversations.json` contains the synthetic-only examples with turn
timings, model-call counts, arguments, minimized results, and verbatim responses.
Its `partial_refreshes` metadata identifies the one updated conversation and
the runtime commit used for that live run.
The previous November 1 English synthetic sample is retained under
[`archive/2026-11-01`](archive/2026-11-01/); it is historical and is not the
current five-conversation submission set.

The separate four-question challenge capture used supplied LOCAL files and is
not included here or in Git. Local/private answers are summarized in the README
without publishing source records; a verbatim-answer review copy stays in the
local ignored `reports/` folder. The original capture remains outside the public
repository.
