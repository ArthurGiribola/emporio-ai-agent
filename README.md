# Empório da Música — AI customer-service agent

A conversational Python agent for the Artefact AI Engineer challenge. It answers
music-store questions through one configurable LLM and validated Python tools.
The project includes a CLI, an optional Streamlit mini-chat, and a Windows
desktop launcher that reuses the same agent.

## What it can do

- Search the 65-product catalog, including category, stock and availability.
- Calculate prices and promotions with Decimal; PIX discounts do not stack.
- Retrieve cited store-policy sections from the supplied PDF.
- Read an order only when its owner matches a trusted startup-bound identity.
- Hold multi-turn conversations while keeping deterministic business facts in
  Python services.
- Run with synthetic public fixtures or authorized files in local mode.

## Architecture

    CLI / Streamlit / Windows WebView
                  |
           Shared Agent
          /             \
   Ollama or Gemini   Validated ToolRuntime
                            |
          Catalog · Pricing · Policies · Orders

The LLM interprets customer requests and selects explicit functions. Python
validates tool arguments, applies filters and calculations, checks order
ownership, retrieves policy evidence, and grounds critical answers. The same
services are reused across interfaces; there is no separate API backend,
multi-agent framework, vector database, or transaction system.

CSV data is loaded into typed records and checked for missing values and
relationships. Prices use Decimal and explicit rounding. Policy retrieval is
section-based with page references and insufficient-evidence handling. Order
access is read-only and exposes no customer contact fields.

## Python requirement

The package metadata declares Python 3.11 or newer. The minimum version itself
was not tested in the final run; the complete suite was run with Python 3.12.15.
Streamlit and pywebview are optional dependencies.

## Quick start: synthetic DEMO

Install Python and Ollama, then create the environment and install the core CLI:

    python -m venv .venv
    # Windows PowerShell
    .\.venv\Scripts\python.exe -m pip install -e .
    # macOS/Linux
    .venv/bin/python -m pip install -e .

Install a local model with tool-calling support and make sure Ollama is running:

    ollama pull qwen3:4b

Run the interactive CLI with public synthetic data:

    # Windows PowerShell
    $env:LLM_PROVIDER = "ollama"
    $env:LLM_MODEL = "qwen3:4b"
    $env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
    $env:LLM_TIMEOUT_SECONDS = "120"
    $env:LLM_MAX_OUTPUT_TOKENS = "2048"
    .\.venv\Scripts\python.exe -m app.cli --data-mode synthetic

The DEMO mode needs no private files and does not save transcripts. Type /quit
to exit or /reset to clear the current conversation. For Ollama cloud-disable
settings, use the [provider guide](docs/PROVIDERS.md).

The public fixtures are bundled with the Python package and are selected
explicitly by `--data-mode synthetic`; the application does not silently fall
back to them when LOCAL files are missing. A fresh checkout therefore needs
only Python, the package dependencies, Ollama and a compatible local model for
the conversational demo. Model generation may vary between runs, while catalog,
price and order facts still come from deterministic demo services. Use the
automated tests below to check behavior without relying on generated wording.
Keep Ollama bound to the local machine for this setup. Gemini is optional and
limited to approved synthetic data; it is not used by the desktop mini-chat.
The original CSV files and policy PDF are intentionally absent from a public
checkout. LOCAL mode requires those files to be supplied separately by an
authorized reviewer and fails clearly when they are missing.

## LOCAL data

LOCAL mode reads the six original CSV files and store policy PDF from the
authorized data directory. Those restricted source files are not included in
Git. To use the CLI:

    .\.venv\Scripts\python.exe -m app.cli --data-mode local

Order access is denied by default. A local demonstration identity can only be
configured at startup and is not production authentication. See
[LOCAL/DEMO mode details](docs/DESKTOP_MODES.md) before enabling order access.

## Interfaces and setup guides

- CLI: instructions above.
- Streamlit browser mini-chat: [interface setup and limits](docs/STREAMLIT_DEMO.md).
- Windows desktop window and double-click launchers:
  [setup, diagnostics, and lifecycle](docs/DESKTOP.md).
- LOCAL/DEMO startup settings and order authorization:
  [mode reference](docs/DESKTOP_MODES.md).
- Gemini synthetic-only provider and local Ollama boundaries:
  [provider setup and privacy](docs/PROVIDERS.md).

## Tests and measured results

Run the automated suite from the repository root:

    .\.venv\Scripts\python.exe -m unittest discover -s tests -v

On November 3, 2026, the complete suite ran on Python 3.12.15 with the
authorized original files available: **313 tests discovered, 307 passed, 6
skipped, no failures**. The six skips were opt-in live provider, scope, and
correctness checks; the official LOCAL questions below were separately tested
with real Ollama. Mocked tests are not counted as live-model runs.

The real qwen3:4b-instruct LOCAL run passed the four official question checks:
the available guitar search returned 12 matches, the Takamine GD20 price came
from the pricing service, the address came from policy section 1.2, and the
general return question used policy retrieval instead of order lookup. The
address value and verbatim LOCAL answers are kept out of public files because
they came from the restricted source PDF.

Previously captured real Ollama runs on synthetic fixtures scored **51/51** on
the primary suite and **48/48** on the paraphrase suite. These finite evaluations
do not guarantee correct behavior for every question. Details and historical
results are in the [final evaluation](docs/FINAL_EVALUATION.md).

## Five genuine DEMO conversations

These are actual local Ollama conversations using synthetic fixtures, not
mocked examples. One earlier return-policy failure is archived; the current
return example was recaptured after the routing correction. A catalog/PIX
follow-up still shows a known model limitation.

1. [Catalog, budget, and PIX](examples/01-catalog-budget-pix.md)
2. [Multi-turn purchase inquiry](examples/02-purchase-multiturn.md)
3. [Return policy and elapsed-day follow-up](examples/03-return-policy-routing.md)
4. [Authorized order](examples/04-authorized-order.md)
5. [Store information and scope](examples/05-store-information-and-scope.md)

See the [example index](examples/README.md) for capture context and the
archived pre-fix transcript.

## Limitations

- Catalog, stock and order data are snapshots, not live inventory or shipment
  systems. No purchase, reservation, refund, cancellation or shipment is made.
- Qwen may occasionally miss a required tool call or lose an ambiguous
  reference. The agent rejects unsupported factual prose or asks for
  clarification; this is safer but can feel like a failed response.
- The source policy contains some conflicting contact details. The agent reports
  uncertainty rather than choosing among inconsistent values.
- DEMO uses fictional catalog, policy and order fixtures. Its return window is
  deliberately different from the supplied LOCAL policy.
- The startup-bound demo identity is for demonstration only, not production
  authentication. Gemini live execution was not verified; cloud use is limited
  to approved synthetic data.
- Context and model attempts are bounded. Hardware, model version and sampling
  can affect latency and wording.

See the [reliability audit](docs/RELIABILITY_AUDIT.md) and
[correctness fixes](docs/CORRECTNESS_FIXES.md) for reproduced defects and
specific remaining risks.

## AI assistance and submission

OpenAI Codex assisted with data inspection, architecture, implementation,
testing and English documentation. Anthropic Claude assisted with an
independent orchestration audit, the catalog-search redesign and multi-turn
evaluation. The author made and accepted the design decisions. Reported tests
were executed; mocked outputs are not described as real model conversations.

The repository has not been pushed or submitted. The challenge materials
contain differing delivery-channel instructions (GitHub link by email and an
English PDF via Google Forms); confirm the required channel and deadline before
submission. Follow the [safe publication checklist](docs/PUBLISHING.md).

## Technical reference

- [Policy retrieval and secure orders](docs/PHASE_2.md)
- [Provider strategy and privacy boundaries](docs/PROVIDERS.md)
- [Windows desktop launcher](docs/DESKTOP.md)
- [Streamlit mini-chat](docs/STREAMLIT_DEMO.md)
- [Final evaluation and repository audit](docs/FINAL_EVALUATION.md)
- [Conversational scope safeguards](docs/SCOPE_FIX.md)
- [Catalog and policy regression evidence](docs/CORRECTNESS_FIXES.md)
