# Actual DEMO conversations

These five conversations were captured on November 3, 2026 with local Ollama
`qwen3:4b-instruct`, using only the approved synthetic DEMO fixtures. The
customer questions, assistant responses, synthetic catalog rows, and tool names
are preserved from that run. They are live model/application outputs, not mocked
tests.

This is an evidence set, not five success stories. It includes three observed
response problems: the catalog/PIX follow-up failed to resolve the listed
product; a return-policy question was routed to order lookup; and its elapsed-day
follow-up failed without retrieving policy evidence. The runner's `error` flag
marks two of those turns; the incorrect order lookup returned an `answered`
status and was identified by reviewing the actual question, tool call, and
response. Do not infer reliability from a single short sample.

| Conversation | Observed behavior |
| --- | --- |
| [Catalog, budget, and PIX](01-catalog-budget-pix.md) | Catalog result is correct; the next-turn “cheapest/PIX” question fails to resolve its reference. |
| [Multi-turn purchase inquiry](02-purchase-multiturn.md) | Stock and PIX facts are grounded; requesting 10 when only 3 are recorded is refused as a completed purchase. |
| [Return-policy routing](03-return-policy-routing.md) | First question incorrectly receives order information; the policy follow-up is not verified. |
| [Authorized order](04-authorized-order.md) | Authorized synthetic order is read-only; missing tracking/delivery fields remain unknown. |
| [Store information and scope](05-store-information-and-scope.md) | Missing opening-hour evidence is disclosed; an unrelated math request is redirected. |

`live-conversations.json` contains the same synthetic-only capture with turn
timings, model-call counts, arguments, minimized results, and verbatim responses.
The previous November 1 English synthetic sample is retained under
[`archive/2026-11-01`](archive/2026-11-01/); it is historical and is not the
current five-conversation submission set.

The separate four-question challenge capture used supplied LOCAL files and is
not included here or in Git. Local/private answers are summarized in the README
without publishing source records; a verbatim-answer review copy stays in the
local ignored `reports/` folder. The original capture remains outside the public
repository.
