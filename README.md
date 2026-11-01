# Empório da Música — customer-service agent

Phase 2 adds section-based policy retrieval and session-bound, read-only order
access to the Phase 1 deterministic data foundation. It does **not** yet include
an LLM, conversational CLI, production authentication, or external integrations.

## Requirements and setup

Python 3.11 or later. The sole runtime dependency is `pypdf==6.10.0`, used for
PDF text extraction. Tests use standard-library `unittest` and pypdf to generate
synthetic documents. Editable installation uses setuptools as a build dependency;
Git is needed only for version control. No API key or `.env` loading is needed
for this phase. The blank LLM variables in `.env.example` are reserved for a
future phase.

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

For source-tree use without editable installation, install the pinned pypdf
dependency first, then run `python -m unittest discover -s tests -v` from the
repository root. Phase 1 catalog and repository modules still use only the
standard library.

## Authorized input data

Place the six original UTF-8 CSVs under `data/`: `categories.csv`, `products.csv`,
`promotions.csv`, `customers.csv`, `orders.csv`, and `order_items.csv`.
CSV headers and types are defined in `app/repository.py`. UTF-8 BOMs are accepted.
Header-only tables are allowed; referenced records must still exist.

The original resources are intentionally excluded from Git. Customer records and
the internal policy PDF must not be published without authorization. Integration
tests skip explicitly when the original CSVs are absent; synthetic tests still
run. To test originals outside this folder, set `EMPORIO_DATA_DIR` in the process
environment. This variable affects integration tests; application code receives
its data directory explicitly. For policy retrieval, also place the authorized original `políticas_da_loja.pdf`
in `data/`. Synthetic PDF tests always run; original PDF integration tests skip
explicitly when it is absent. No extracted source text is saved to the repository.

## Using the implemented Python API

These commands can be entered in a Python shell from the repository root:

```python
from decimal import Decimal
from app.repository import Repository
from app.services import CatalogService

repository = Repository("data")
catalog = CatalogService(repository)
products = catalog.search_products(category_id=5, max_price_brl=Decimal("1000"))
quote = catalog.get_price_quote(127, payment_method="pix")
print(quote.final_price_brl, quote.available)
```

This is an API usage example, not a fabricated customer conversation. Authentic
conversation transcripts will be produced after the agent exists.

## Implemented behavior and decisions

- Frozen dataclasses provide explicit records. Public catalog indexes and product
  specifications are read-only mappings. CSVs are loaded once per repository
  instance; construct a new instance to reload them.
- Startup validation rejects invalid required values, unsupported statuses,
  malformed JSON, non-finite/negative prices, fractional quantities, duplicate
  primary/composite keys, incorrect CSV field counts, and unresolved references.
  IDs/counts are bounded to 12 decimal digits; monetary values allow up to 12
  integer digits and cent precision. These are implementation limits, not store
  policies. Discount percentages must be between 0 and 100 inclusive.
- Empty tracking, estimated delivery, and order notes become `None`. Missing
  required values are errors. Error messages identify file/field/line without
  echoing customer values.
- Data-quality warnings preserve contradictions rather than silently rewriting
  source records: duplicate customer emails, non-active products with stock,
  multiple active promotions, missing order items, and historical totals that
  differ from current catalog sums.
- Limited heuristics flag explicit brand and key/string-count disagreements.
  They do not prove all other descriptions correct, and do not automatically
  select an authoritative attribute. Check `repository.product_warnings(id)`
  before recommending products; future tool responses must include these flags.
- Availability means `status == "active" and stock_quantity > 0`. It excludes
  discontinued and coming-soon records even when their stock is positive.
- Search AND-matches normalized terms across name, description, and category;
  ignores case/accents; maps common Portuguese instrument singular/plural names;
  and sorts by list price then ID. Price bounds are inclusive **list-price**
  bounds, not discounted budgets. This is substring search, not semantic search.
- Only promotions explicitly marked `1` are active. Campaign names and today's
  date cannot establish validity without supplied validity dates. Promotion
  listings default to available products; callers may inspect unavailable offers.
- Quotes use `Decimal` and explicit `ROUND_HALF_UP` cent rounding in a local
  precision context. An active promotion takes precedence; otherwise PIX receives
  5% off list price. PIX never stacks with a promotion. These rules reflect manual
  sections 3 and 6.2; rounding is an implementation convention. Multiple active
  promotions for one product block quoting instead of guessing precedence.
- Unavailable items can have a nonbinding informational quote, always marked
  `available=False`. Every quote states that freshness is unknown. There are no
  live stock checks, reservations, purchases, or guaranteed offers.
- Recorded order totals remain authoritative. Current product prices cannot
  reconstruct past purchases because historical unit prices are absent.

A database, dataframe library, vector store, agent framework, and frontend would
add dependencies without solving the current requirements. The repository separates
source validation from business rules so later function-calling tools can use
these services without letting the model calculate prices or query raw files.

## Policy retrieval (Phase 2)

```python
from app.policies import PolicyRetriever

policies = PolicyRetriever("data/políticas_da_loja.pdf")
evidence = policies.search("Posso acumular PIX com desconto promocional?")
print(evidence.status)
for section in evidence.sections:
    print(section.number, section.pages)
```

The retriever extracts text in memory, recognizes the supplied manual's numbered
headings, joins page continuations, and preserves 1-based physical PDF page
references. Titles and query examples remain Portuguese because they are source
metadata and customer inputs; project explanations and diagnostics are English.
It ignores recurring headers/footers and distinguishes numbered service steps
from section headings. Its explicit document profile fails on unsupported
headings or changed recognized titles rather than silently guessing.

Normalized Portuguese topic patterns cover returns/refunds, warranties/defects,
payments/installments, shipping/tracking, promotions, opening hours, complaints,
contacts, and privacy. Related sections are returned together, including warranty
context for defect exchanges and promotional restrictions for PIX.

Results contain reference-only sections, structured issues, and limitations:

- `evidence_found`: relevant reference material was found; it is not a customer
  answer, eligibility decision, or verification of current operational facts.
- `needs_review`: source conflicts, scope ambiguities, or live-schedule uncertainty
  require clarification before a definitive answer.
- `insufficient_evidence`: no supported topic, missing required sections, or a
  recognized unsupported detail such as an individual shipping quote, payment
  method, product-specific warranty, or order/refund status.

Detectors compare contact numbers/email spellings, installment minimums, local
shipping threshold boundaries, and tracking-description/example lengths. Return
exclusion scope and exchange-versus-warranty context are explicit caution flags,
not claims that customer legal rights have been determined. Detector coverage is
limited and cannot establish that the manual has no other ambiguities.

There are no embeddings or vector database. Sixteen explicit original-document
question/section checks measure coverage of the supported topics; they are not
a general semantic accuracy benchmark. Unrecognized paraphrases may return
insufficient evidence. PDFs must contain extractable text, no blank/scanned
pages, at most 100 pages, and at most 10 MiB; OCR and arbitrary PDF layouts are
outside scope. Encrypted/malformed/missing documents fail clearly. Do not expose
all internal policy sections or diagnostics indiscriminately to customers.

## Privacy boundary and demo order access (Phase 2)

```python
from app.orders import DemoSessionConfig, OrderService

# Trusted local application startup ONLY. Never construct this from chat/tool args.
orders = OrderService(repository, DemoSessionConfig(enabled=True, customer_id=1))
result = orders.lookup_order(1)  # May be unavailable: ownership is checked here.
```

No demo identity is active by default. An identity requires explicit opt-in and
an existing customer ID in trusted local configuration. One frozen service is
created per session. Its only lookup argument is `order_id`; no request can
supply a replacement identity. Chat strings are not parsed as authentication.
Constructors/configuration must never be exposed as future LLM tools.

Ownership is verified inside the service before constructing order output.
Anonymous requests, foreign orders, nonexistent orders, and malformed IDs return
the **same response body**, with no order ID echo or existence distinction. This
is not a claim of constant-time execution. Authorized output includes recorded
status, total, dates/tracking when supplied, and product names/quantities. It
excludes customer ID, names, email, phone, address, payment details, and free-text
notes. Missing fields remain `None`; actual delivery and historical unit prices
are explicitly unknown. Current catalog prices never replace historical totals.
Cancelled orders remain cancelled, and there are no mutation methods or claims
that refunds/returns/cancellations/shipments were initiated.

This is **local demonstration identity binding, not production authentication**.
Frozen dataclasses and underscore-prefixed repository attributes prevent routine
misuse, not hostile Python code in the same process. Production needs a verified
session adapter, access controls, and operational logging/rate limits appropriate
to its environment. Repository objects and global diagnostics are not tool
responses. No public customer search or order-list endpoint exists.

No customer values, full policy text, or credentials are copied into tests or
documentation. Synthetic fixtures use `example.invalid` addresses and generated
PDFs. Raw files, virtual environments, and build output remain ignored. This phase
creates a local commit only; publication is a separate decision.

## Validation

See `docs/PHASE_2.md` for current executed commands/results and limitations, and
`docs/PHASE_1.md` for the prior phase record. Synthetic temporary CSV/PDF tests
run without restricted source files. Optional integration tests validate the
original CSVs and policy PDF; missing resources are reported as skips.

## AI assistance and submission status

Codex assisted with initial inspection, architecture discussion, Phase 1 and
Phase 2 code, tests, and English documentation. Test results are produced by executing the
suite, not inferred from code. Human review remains necessary, particularly for
source conflicts and authorization design.

The original challenge brief and recruiting email are not in this starter. The
starter reports both a public GitHub submission and an English PDF via Forms;
confirm the original instructions before final submission. The complete agent,
final README, genuine transcripts, and any required PDF remain future work.
