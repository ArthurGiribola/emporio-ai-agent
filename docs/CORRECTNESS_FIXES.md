# Correctness fixes after real Ollama conversations

## Catalog failure: verified causes

The exact customer question was reproduced with the original CSVs and actual
local qwen3:4b-instruct inference before changes. The model requested
search_products(query="violão", max_price_brl="1000.00"), without category_id.
The service searched descriptions too. Product 128 is category 9 (Ukuleles), but
its description mentions violão; it was therefore the fifth of 13 matches.

The wrapper hard-capped every search at five records, exposed no exhaustive
option, and returned total_matches=13/truncated=true. Final model prose then
incorrectly explained the five records as the only ones within budget, although
the budget had already filtered all 13. This occurred with a fresh session;
previous-turn context was not necessary to reproduce the failure.

## Catalog correction

Category labels are resolved against actual category records and become strict
filters, separate from description matching. Explicit customer category/budget
constraints override conflicting model arguments and are visible in diagnostics.
all_results is validated independently of the model; explicit requests for all
set it deterministically. Compact rows allow all 61 available snapshot products
under the 12K output ceiling; oversized future outputs remain explicitly partial.
Counts, applied filters, sort order, and truncation are exposed accurately.

Catalog-list prose is rendered from returned evidence, with natural Portuguese
prices/labels and honest partial/full wording. This prevents the model from
adding a wrong-category product or inventing a completeness explanation. Critical
catalog requests require fresh current-turn evidence, not unrelated prior tools.

## Verification before the catalog commit

Six new regressions failed against the old implementation and passed after the
fix. Original-data regression verifies the exact 12 IDs in ascending price order.
The existing full suite still passes. Actual local inference was rerun after a
ukulele turn; the requested query was "guitar", while effective arguments used
category 5, budget 1000, all_results=true. All 12 matching violões were returned
and displayed, with no product 128 or internal field names.

## Return-policy investigation

Section 4.1 was retrieved in full (395 characters, page 4), including the seven-day
request window and refund conditions. A first fresh run did not reproduce the
reported opening denial. Two further fresh runs did reproduce a semantic variant:
the model said the customer's five days were not aligned with the seven-day
policy. A prior warranty/returns conversation produced a correct comparison but
added an unsupported refund-start assumption. These are actual model executions,
not mocked reproductions. The original exact opening sentence was not observed.

The arithmetic and final policy interpretation were left entirely to unconstrained
model prose. Tool queries also sometimes dropped the customer's five-day detail.
The permissive orchestration accepted any earlier tool success as sufficient
evidence, without a fresh policy lookup or a consistency check on final prose.

## Return-policy correction

The original customer question now supplies the channel/timing context to the
policy tool even when the model rewrites its query. Simple online-withdrawal
questions use sections 4.1 and 4.4 rather than unrelated defect/warranty material.
An explicit parser extracts the affirmative receipt-window rule from the source;
no seven-day constant is used. The refund clause and its business-day figure,
product conditions, and return-shipping statement also come from section 4.1.

Python compares the customer's elapsed calendar days with the extracted window.
This is explicitly a timing assessment, not eligibility or return/refund approval.
A narrow deterministic renderer replaces model prose for this critical case,
with page references and source conditions. Contradictory model text is not
retained as the displayed assistant answer in subsequent conversation history.
Refund wording is preserved without inventing a validation/approval start date.

Missing/conflicting rule grammar, unknown purchase channel, purchase-date rather
than receipt-date clocks, contradictory receipt dates, nonreceipt, and business-
day conversion requests fail closed or ask for clarification. A synthetic eleven-
day policy and three-business-day refund test prove the values are source-derived.
These are focused guards, not a general semantic proof for all policy questions.

## Regression and real-model verification

- Six catalog methods and nine return methods include synthetic and optional
  original-resource checks; existing tests remain in the suite.
- Fake contradictory model prose reproduces the exact reported denial as a
  regression input, clearly distinguished from actual model execution.
- Real qwen3:4b-instruct conversations were rerun for the exact catalog question
  after a ukulele turn, and the exact five-day return question after a warranty
  turn. Both correctness assertions passed against actual tool evidence.
- Additional genuine fresh conversations at five, seven, and eight days verified
  inclusive timing boundaries: within, within, and outside the stated window.
- Even a genuine eight-day model response made an overbroad eligibility denial;
  the displayed guard correctly limited the conclusion to the specified time
  window and referred other procedures/conditions for review.

Exact final suite counts and commit IDs are recorded in the delivered report.
Live checks can be reproduced locally with:

```powershell
$env:EMPORIO_RUN_LIVE = "1"
$env:OLLAMA_MODEL = "qwen3:4b-instruct"
.\.venv\Scripts\python.exe -m unittest tests.test_live_correctness -v
```

Or run the full suite with those variables set. Gemini remains skipped unless
its synthetic-only free-tier configuration is provided. No external provider
was used for source-data correctness tests.

## Diagnostics and privacy

Agent accepts an optional trusted local observer, recording requested/effective
tool arguments, minimized tool evidence, model text, and guarded final text. It
has no automatic file/network sink and is disabled by default. Raw traces from
the authorized internal manual remain local and are not committed. No customer
record or complete policy document was sent to an external provider. No push.

## Final executed results (November 1, 2026)

| Run | Passed | Skipped | Failures |
| --- | ---: | ---: | ---: |
| Full suite, Python 3.15.1, live enabled | 119 | 1 (Gemini) | 0 |
| Full suite, Python 3.12.14, default offline mode | 116 | 4 live checks | 0 |
| Full suite, no private resources, offline mode | 103 | 17 | 0 |
| Dedicated real qwen3:4b-instruct correctness checks | 2 | 0 | 0 |

All full runs discovered 120 methods; subcases are not counted as separate
methods. The live-enabled suite took 37.249 seconds in the recorded run; this
is an observed test duration, not a latency guarantee. The Gemini skip reflects
missing local API/free-tier configuration, not a claim of Gemini validation.

Catalog fix commit: `832a671`. Return correction is a separate focused fix commit.
No source data or raw traces are committed, and nothing was pushed.
