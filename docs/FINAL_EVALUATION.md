# Final evaluation — November 1, 2026

This report records the November 1 audit state and its test counts. The
November 3 Qwen capture and current example set are summarized in the README and
[example index](../examples/README.md); do not treat the historical counts below
as the current suite result.

## Scope and actual execution

Phase 4 evaluated the existing one-model CLI architecture; no framework, UI,
vector database, paid service, or new business workflow was introduced.

The complete suite with original authorized local files and live tests enabled
ran on Python 3.15.1: **124 tests, 123 passed, 1 skipped**, no failures/errors,
58.508 seconds. The skip was Gemini: no API key/free-tier confirmation configured.
Live Ollama synthetic pricing and the original catalog/return regressions passed.
Mocked provider contracts and loopback HTTP stub tests remain explicitly separate
from actual model inference. Default tests do not contact a model.

```powershell
$env:EMPORIO_RUN_LIVE = "1"
$env:OLLAMA_MODEL = "qwen3:4b-instruct"
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

## Five actual English conversations

See [the example index](../examples/README.md) and its raw structured JSON.
Ten turns completed with answered status and **17 actual model requests**.
Six displayed answers were rendered by application grounding guards after live
inference, and four were model-written. These are scripted synthetic scenarios
with actual inference, not fabricated customer exchanges or mocked tests.

- Catalog/promotion: both available fixtures listed in ascending order; product 1
  PIX price 90.09 from base 100.10 and 10% promotion, no extra PIX discount.
- Unavailable product: product 2 has zero recorded stock; available alternatives
  supplied without claiming a live inventory update.
- Policy: retrieved synthetic eleven-day reference; unknown refund deadline and
  initiation not asserted. This intentionally fictitious reference is not the
  original store's seven-day rule.
- Authorized order: recorded total 99.00 preserved; absent tracking and delivery
  dates left unknown rather than recalculated from current prices.
- Denied order: uniform denial for order 2; conversational identity change refused.

Recordings identify runtime commit 94f672b45ffa7144c04952caeb8e5e2ab8014f05,
model digest, template hash, parameters, fixture hash, timestamps, actual tool
arguments/evidence, and answer origins. No private dataset was used for them.
The local qwen3:4b-instruct tag is not assumed publicly downloadable; README
uses public qwen3:4b. Sampling is not fixed and repeated wording can differ.

This is a small observed evaluation, not a benchmark or proof of general answer
accuracy. The policy follow-up still mentions internal evidence labels; its
verbatim wording is preserved as a presentation limitation. No real refund,
return, purchase, identity change, or shipment was performed.

## Genuine fixes discovered during evaluation

Preflight runs are not relabeled as successful final recordings. They exposed
English "all" being interpreted as a literal search term, an invented model
budget, English policy synonyms missing retrieval, a non-stacking PIX rule being
worded as a payment prohibition, and technical field labels in order answers.

- f6210ea: English query normalization, broad-request filter binding, and policy
  query synonyms. Full suite before commit: 122 tests, 118 passed, 4 skipped.
- 94f672b: source-based quote/order wording and fresh explicit-ID evidence;
  rejected no-tool assertions kept out of conversation memory. Full suite before
  commit: 124 tests, 120 passed, 4 skipped.

These are small corrections to existing boundaries, not a redesign. Synthetic
regressions cover the observed failures. Final conversations were captured only
after the runtime fixes were committed.

## Reproducibility without private sources

A Git archive of runtime revision 94f672b was exported without any private
CSVs/PDF, .env, or Git metadata. A fresh Python 3.12.14 virtual environment
installed it with `pip install .` (non-editable); pypdf and the package installed
successfully. Cloud credentials and data-directory environment overrides were
removed from child processes.

- Complete public suite: **124 tests, 107 passed, 17 skipped**, no failures/errors,
  5.508 seconds. Skips: 13 private-resource tests and four opt-in live tests.
- Isolated `python -I` from an empty directory loaded `app` from the fresh
  environment's site-packages and instantiated the packaged synthetic fixtures.
- Public qwen3:4b actual function-calling smoke: **2 tests, 1 passed, 1 skipped**
  (Gemini key absent), 50.878 seconds. This independently verifies the publicly
  named README model rather than assuming the custom instruct tag is available.

The installed CLI was also run from an empty directory using public qwen3:4b.
The first run at the default 1024 output-token limit returned a sanitized
"Ollama response was incomplete" error, not an answer. With the README's explicit
2048-token budget, a real English pricing turn returned 90.09 and correctly
explained PIX non-stacking, then exited through /quit. Both outcomes are retained
in the local evaluation record. A zero CLI exit code alone is not treated as
proof of a successful answer. Hardware/model/sampling can still cause failures.

Final documentation adds only evidence, capture tooling, and instructions; runtime
code, fixture, tests, and packaging match the tested runtime revision.

## Repository and security audit

The audit checks all historical file trees and every local Git blob, including
unreachable blobs, plus raw commit headers/messages. It compares seven original
CSV/PDF fingerprints, 158 original customer name/contact/tracking strings, and
credential patterns (Google/OpenAI/GitHub/AWS keys, private keys, credential URLs).
Configured secret values are checked when present. No original data or actual
secret values are printed in public reports.

At runtime revision 94f672b: nine commits, 76 reachable/local blobs, zero
unreachable blobs, **zero findings**. No historical CSV/PDF/secret .env paths or
PDF binaries were found. A final scan is also performed after the documentation
commit, with its exact HEAD/counts in the delivery report.

All nine development commits are nonempty and linear; retained reflogs contain
no amend/rebase/reset events. The phase commits and executed test records support
genuine incremental development; Git inspection cannot prove every prior manual
activity. The first two messages predate the conventional-message rule and are
preserved. There is one consistent author/committer identity with a non-noreply
email: owner review is required before making that metadata public. It is not a
customer-data finding, and history was not rewritten to conceal it.

The scan is pattern/fingerprint based, not mathematical proof against transformed
secrets or all PII. Synthetic .invalid contacts are intentionally fictitious.
Source-grounding and immutable ownership checks remain in Python; Gemini remains
restricted to approved synthetic content/filtered intents. At the time of this
November 1 audit, no remote was configured and nothing was pushed or submitted.
The repository was linked to a GitHub remote afterward; check current branch and
remote state before publication. No submission occurred during this historical
audit.

## README review and remaining delivery questions

README documents installation, real interactive local use, synthetic Gemini
restrictions, architecture/trade-offs, testing layers, source limits, immutable
demo identity versus production authentication, and concise accurate Codex
assistance disclosure. Original resources are optional and excluded from Git.

Before submission, confirm the actual deadline and whether both GitHub and an
English PDF via Forms are required. Original brief/email are unavailable for
independent verification; the local planning document records that discrepancy.
No final submission PDF is claimed. Do not redistribute originals without
permission. Gemini live eligibility is unverified without a configured free-tier
project, but the local route requires no paid API. General model prose and the
remaining policy-label wording remain limitations. See [publication instructions](PUBLISHING.md).
