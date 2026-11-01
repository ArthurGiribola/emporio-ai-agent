# Phase 2: Policy Retrieval and Secure Order Access

## Completed scope

Implemented lightweight section-based policy retrieval and a read-only order
service bound to a trusted local demo session. No LLM, conversational CLI,
frontend, vector database, order mutations, or external integrations were added.
All 33 Phase 1 tests and their implementation remain unchanged.

## Files created

- `app/policies.py`: PDF extraction, numbered sections/page references,
  Portuguese topic/synonym retrieval, related evidence, conflict/caution flags,
  and insufficient-evidence results.
- `app/orders.py`: explicit local demo configuration, immutable session-bound
  order service, ownership checks, minimal response records, uniform denials.
- `tests/policy_helpers.py`: generated synthetic PDFs in temporary directories.
- `tests/test_policies.py`: 14 policy test methods with multiple subcases.
- `tests/test_orders.py`: 11 order/security test methods with multiple subcases.
- `tests/test_phase2_supplied_data.py`: seven original-resource integration tests.
- `docs/PHASE_2.md`: this report.

## Files modified

- `pyproject.toml`: version 0.2.0; added the sole runtime dependency,
  `pypdf==6.10.0`.
- `README.md`: current setup, Python API examples, policy statuses, security
  boundary, limitations, and AI-assistance disclosure, all explained in English.

Phase 1 code/tests, original CSVs, the policy PDF, secret placeholders, and Git
exclusions were not changed. No source PDF/CSV or extracted source-text cache is
committed. Source section labels and Portuguese customer-question examples are
metadata/test inputs, not English documentation translations of the manual.

## Policy design and behavior

The retriever reads the authorized text PDF into memory, recognizes the supplied
manual's structural profile, and preserves 28 numbered sections plus its cover.
Page numbers are physical PDF pages, starting at 1. For example, the original
shipping section spans pages 4-5, service flow spans 6-7, and privacy spans 7-8.
Continuation text stays attached to its section. Numbered service steps are not
mistaken for new policy headings.

Normalized Portuguese topic patterns cover returns/refunds, warranties/defects,
payments, shipping/tracking, promotions, hours, complaints, contacts, and privacy.
Queries may retrieve several related sections. PIX/promotional questions retrieve
payment and non-stacking evidence without unrelated installment conflict noise.

Every result and section is marked reference-only. No extracted text is executed
or interpreted as application instructions. The retriever returns evidence, not
a synthesized customer answer, transaction permission, or legal determination.
Statuses distinguish evidence found, review required, and insufficient evidence.
Unsupported payment methods, individual shipping quotes, product-specific
warranty terms, personal refund/order status, and missing section evidence are
handled conservatively. Unsupported phrasing can also yield insufficient evidence.

Contact/email differences, installment discrepancies, and the undefined exact
local-shipping threshold are detected from extracted text. Return exclusions and
exchange/warranty interactions are separately labeled scope cautions. These
checks are deliberately limited, not a complete logical analysis of policy law.
Tracking-format/example disagreement is detected when present in synthetic data.
**Correction to the initial analysis:** the original manual's example and supplied
tracking codes conform to its stated length; no tracking-format conflict is
reported against the original PDF.

Lexical retrieval is transparent and sufficient for the measured topic checks.
Sixteen Portuguese original-document questions retrieved their expected section
sets. This is a small coverage check, not evidence of general semantic accuracy,
and does not justify adding a vector database.

## Order security and behavior

`DemoSessionConfig` is trusted startup configuration, not conversational input.
Demo mode is disabled by default and requires explicit opt-in plus a valid local
customer ID. One frozen `OrderService` is constructed per session. Only
`lookup_order(order_id)` should be exposed in future tool schemas; no identity,
constructor, raw repository, or configuration object may be exposed as a tool.

The service checks ownership before constructing an order view. Anonymous,
foreign, nonexistent, and malformed order requests share the same response body.
There is no order-existence distinction or raw ID echo on denial. This is not a
constant-time guarantee. Chat strings, replacement-identity keyword arguments,
and attempts at normal attribute reassignment cannot rebind the session.

Authorized views include recorded status/total, order date, supplied tracking
and estimated delivery, and product names/quantities. They omit customer IDs,
customer names, email, phone, address, payment details, and all free-text notes.
Missing dates/tracking remain `None`; actual delivery and historical unit prices
are explicitly unavailable. Recorded historical totals are never recomputed
from today's catalog prices. Cancelled orders retain their recorded status.
No refund, return, cancellation, shipping, or identity-mutation method exists.

This is demonstration identity binding, **not production authentication**. Trusted
Python can still construct a new demo service or access private memory; frozen
records are not a sandbox. Production requires a verified identity/session adapter.
No LLM is integrated, so model-level prompt-injection resistance is not claimed.

## Executed verification — November 1, 2026

- Windows project virtual environment: Python 3.15.1.
- Compatibility check: bundled Python 3.12.14, with the same pypdf version.
- Python 3.11 remains the declared minimum but was not available for execution.
- `.\.venv\Scripts\python.exe -m pip install -e .`: successfully installed
  `emporio-agent==0.2.0` and `pypdf==6.10.0`.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`:
  **65 passed, zero failures, zero skipped** on the original resources.
- Full suite on Python 3.12.14: **65 passed, zero failures, zero skipped**.
- Full suite with `EMPORIO_DATA_DIR` set to an absent directory:
  **54 passed, 11 explicitly skipped, zero failures**. Seven CSV integration
  methods and four PDF integration methods require authorized originals.
- `.\.venv\Scripts\python.exe -m pip check`: no broken requirements.
- All Phase 1 implementation and test files remain unchanged.

Coverage includes return/refund and warranty synonyms, PIX/promotion restrictions,
source conflicts, page continuations, unsupported questions, missing/invalid PDFs,
encrypted/blank PDFs, missing policy evidence, missing/malformed CSVs, authorized
lookup, cross-customer denials, identity spoofing, missing fields, cancelled orders,
privacy omissions, and historical totals. Original-order authorization checks
exercise all 20 supplied orders. Method counts exclude individual subcases.

## Known limitations

- PDF parsing targets the supplied numbered-heading profile. Encrypted, empty,
  scanned/blank, malformed, unsupported-heading, over-100-page, or over-10-MiB
  PDFs are rejected. OCR and general PDF layout recovery are outside scope.
- Topic matching and ambiguity detectors are explicit heuristics. They can miss
  unfamiliar paraphrases or unmodeled conflicts; found evidence is not a complete
  answerability proof. Source freshness, holidays, and individual eligibility
  are not verified.
- Orders are static snapshots with missing actual delivery times and historical
  line prices. No carrier, shipping quote, return, refund, or ticket integration
  exists.
- The demo identity must never be inferred from chat, email, or an order number.
  Python-process isolation and production identity verification are separate work.
- The original assessment brief/email, redistribution permissions, and final
  submission-format discrepancy remain unresolved.

## Recommended Phase 3

Add the conversational CLI and a single tool-capable LLM using an explicit,
bounded function-calling loop. Expose only constrained catalog/pricing/policy
functions and the already-bound order lookup. Validate schemas, reject extra
identity arguments, serialize Decimal/dates deliberately, keep retrieved text
in reference-data fields, preserve page citations/warnings, and never claim
an action was taken. Add deterministic adapter tests and genuine model runs
for grounded responses, refusal/clarification, and attempts to override identity.
Choose provider/model and configure credentials locally before those live runs.
