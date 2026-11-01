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
model prose. Further safeguards and regressions are being implemented separately.

## Diagnostics and privacy

Agent accepts an optional trusted local observer, recording requested/effective
tool arguments, minimized tool evidence, model text, and guarded final text. It
has no automatic file/network sink and is disabled by default. Raw traces from
the authorized internal manual remain local and are not committed. No customer
record or complete policy document was sent to an external provider. No push.
