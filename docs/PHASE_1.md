# Phase 1 implementation report

## Scope

Completed the deterministic data foundation only. No LLM, conversational CLI,
policy retrieval, authenticated order tool, frontend, or external service exists.

## Files created

- `pyproject.toml`: package metadata; setuptools build backend; zero runtime dependencies.
- `app/__init__.py`: package declaration.
- `app/models.py`: frozen typed records and quote/warning models.
- `app/repository.py`: six-file loading, field/schema validation, relationships,
  read-only public catalog indexes, redacted diagnostics, quality warnings.
- `app/services.py`: normalized product search, availability filtering, active
  promotion listing, deterministic Decimal quotes.
- `tests/__init__.py`: test package declaration.
- `tests/helpers.py`: synthetic CSV fixture generation.
- `tests/test_repository.py`: 15 test methods, including parameterized invalid
  inputs and all five foreign-key relationships.
- `tests/test_services.py`: 14 test methods for search, availability, promotions,
  pricing, rounding, and argument validation.
- `tests/test_supplied_data.py`: four optional original-snapshot integration tests.
- `docs/PHASE_1.md`: this report.

## Files updated and retained

- `README.md`: English setup, usage, decisions, privacy boundaries, limitations,
  AI-assistance disclosure, and delivery status.
- `.gitignore`: retained raw CSV/PDF and secret exclusions; added packaging output
  and local planning-input exclusions.
- Existing `.env.example`, English `docs/DATA_NOTES.md`, and empty-directory
  placeholders are retained as starter files.
- Original data files and policy PDF were not modified. The original Portuguese
  planning prompt remains local and is excluded from project deliverables.

## Executed verification — November 1, 2026

Environment: Windows PowerShell, project virtual environment using Python 3.15.1.
A second interpreter compatibility check used bundled Python 3.12.14.
Python 3.11 is the declared minimum but was not available for execution here.

1. `python -m venv .venv`: succeeded.
2. `.\.venv\Scripts\python.exe -m pip install -e .`: built and installed
   `emporio-agent==0.1.0` successfully.
3. `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`:
   **33 tests passed, zero failures, zero skipped** (0.479 seconds in the recorded
   successful run). Includes all four checks against the supplied original CSVs.
4. Same suite with `EMPORIO_DATA_DIR` pointing to an absent resource directory:
   **29 passed, four integration tests explicitly skipped, zero failures**
   (0.426 seconds). This checks behavior without restricted resources.
5. Bundled Python 3.12.14: same full suite passed, **33 tests, zero skipped**.
6. `.\.venv\Scripts\python.exe -m pip check`: no broken requirements.

The first run had one real failure: singular `violao` did not match plural
`violoes`. A controlled instrument-name alias map fixed that behavior before the
successful runs. Test method counts exclude individual `subTest` cases.

Original-data checks confirm: 65 products, nine categories, 25 promotions,
50 customers, 20 orders, 22 items; 12 available violões within the tested R$1,000
list-price budget; four expected promotional prices; no PIX stacking; missing
tracking/delivery fields preserved; discontinued/coming-soon stock conflicts;
duplicate email warning; and two historical-total discrepancies.

## Interview rationale

The standard library is sufficient for small local CSV snapshots. Explicit
frozen records make types understandable without an ORM or dataframe framework.
Business rules are separated from parsing, allowing future function-calling
schemas to delegate calculations to trusted Python code. Decimal and explicit
rounding make currency behavior reproducible. Invalid structure fails early;
credible but inconsistent records remain visible with warnings. No historical
prices, availability timestamp, or identity verification are invented.

## Known limitations and remaining decisions

- The data has no trusted freshness timestamp, so quotes are nonbinding snapshots.
- Search is normalized substring matching with a small explicit alias map;
  budgets use inclusive list prices, not promotional prices.
- Attribute-conflict detection covers only explicit brand and numeric key/string
  contradictions. It cannot validate all descriptions or material specifications.
- Multiple active promotions block quoting pending source clarification. No
  installment, mixed-payment, freight, refund, or transaction calculations exist.
- Underscore-prefixed order/customer collections are internal Python APIs, not a
  security boundary. No order information may be exposed until an ownership
  check and trusted session identity are implemented.
- Source-policy ambiguities, redistribution permissions, the missing original
  challenge/email, and final submission format remain unresolved.
- The virtual environment and generated packaging metadata are local and ignored.

## Recommended next phase

Implement section-based policy extraction/retrieval and the demo session identity
plus authorized read-only order service, with focused tests for grounding,
conflicts, denied cross-customer access, and missing order fields. Keep LLM
integration as a separate later phase after these deterministic boundaries pass.
