# Empório da Música — customer-service agent

Phase 1 implements the deterministic Python data foundation for the Artefact
challenge. It does **not** yet include an LLM, conversational CLI, order lookup,
policy retrieval, or external integrations.

## Requirements and setup

Python 3.11 or later. There are **no runtime or test dependencies** outside the
standard library. Editable installation uses setuptools as a build dependency;
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

Alternatively, run `python -m unittest discover -s tests -v` directly from the
repository root; installing the package is optional for source-tree use.

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
its data directory explicitly. The PDF is not read or needed in Phase 1.

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
add dependencies without solving a Phase 1 requirement. The repository separates
source validation from business rules so later function-calling tools can use
these services without letting the model calculate prices or query raw files.

## Privacy boundary

Customers and orders are loaded only into private repository collections for
validation. There is deliberately no public customer search or order lookup tool.
Python underscore attributes are a code convention, **not a security sandbox**.
Future order tools must enforce application-level authenticated ownership before
returning minimal fields. Names, email addresses, and order IDs are not identity
proof. Global diagnostics must not be exposed as customer-facing order metadata.

No customer values, full policy text, or credentials are copied into tests or
documentation. Synthetic fixtures use `example.invalid` addresses. Raw files,
virtual environments, and build output are ignored. Public publication is a
separate decision; this phase creates only a local commit.

## Validation

See `docs/PHASE_1.md` for executed commands, actual results, known limitations,
and the next proposed phase. Unit tests use synthetic temporary CSVs; four
optional integration tests validate the authorized original snapshot.

## AI assistance and submission status

Codex assisted with initial inspection, architecture discussion, Phase 1 code,
tests, and English documentation. Test results are produced by executing the
suite, not inferred from code. Human review remains necessary, particularly for
source conflicts and authorization design.

The original challenge brief and recruiting email are not in this starter. The
starter reports both a public GitHub submission and an English PDF via Forms;
confirm the original instructions before final submission. The complete agent,
final README, genuine transcripts, and any required PDF remain future work.
