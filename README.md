# Empório da Música — Python customer-service agent

An interactive text agent with one configurable LLM, explicit function calling,
and deterministic Python catalog/pricing/promotion/policy/order tools. Ollama runs locally; Gemini
3.1 Flash-Lite is the configured free-tier alternative for approved synthetic data.
No paid API, agent framework, separate frontend/backend, or vector database is required.
An optional local Streamlit demonstration reuses the same agent; the CLI remains available.

## Architecture and decisions

`cli.py -> Agent -> native provider adapter -> validated ToolRuntime -> services`

- CSVs load once into typed records; relationships and required values are checked.
  Invalid structure fails early; credible source inconsistencies remain warnings.
- Availability requires active status and positive recorded stock. Prices use
  Decimal and explicit HALF_UP cent rounding. An additional PIX discount never stacks with promotions; the promotional price still applies when paying by PIX.
- Section-based PDF retrieval preserves section numbers/pages, joins continuation
  pages, retrieves related rules, and reports conflicts/insufficient evidence.
- Order ownership is checked inside a read-only service bound at startup.
  Recorded historical totals are preserved; missing fields remain unknown.
- Each non-greeting turn starts with one structured scope check using the same
  configured LLM. Python requires a valid shop decision before business tools or
  answers; unrelated requests receive a polite Portuguese/English redirect.
  Uncertain/malformed decisions ask for clarification and are not stored in memory.
  Only recent customer questions resolve genuine follow-ups; old tool evidence
  cannot authorize an unrelated topic. Gemini projection still happens first.
- After that check, each turn allows at most four business-model requests and six
  business tool calls: five total model requests including scope. This preserves
  the existing grounding-recovery budget at the cost of one extra round trip. Memory
  retains at most four complete exchanges, trims whole exchanges, and enforces
  character limits. `/reset` clears context without changing the bound identity.
- Native tool-call responses and Gemini thought signatures are preserved. Tool
  names/arguments are validated independently of model schemas. Decimal/dates
  serialize explicitly. Output sizes, HTTP timeouts, and response sizes are bounded.

The only core CLI runtime dependency is pypdf 6.10.0; Streamlit is an optional UI extra. Python's standard library handles
CSV, JSON, currency, HTTP, and tests. Direct native REST adapters keep protocol
behavior visible without provider SDK dependencies.

## Install

Python 3.11+ and Git. Tested here on Python 3.15.1 and 3.12.14; 3.11 was not
available for execution. From the repository root in Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On macOS/Linux replace the Python executable with `.venv/bin/python`. The CLI
entry point is also installed as `emporio-agent`. Environment configuration is
read from the process; `.env.example` is reference material, not an auto-loaded
secret file.

## Real interactive conversation with local Ollama

Install [Ollama](https://ollama.com/download) and download a model with native
**tools** capability. `qwen3:4b` is the suggested starting model. Check adequate
RAM/VRAM for weights plus the configured 16K context; CPU-only inference can be
slow. Model installation requires a download, but inference can then stay local.
The application checks tools capability and rejects cloud/remote models. It
never installs models automatically.

In a server terminal, after closing any existing Ollama instance so it picks up
local-only configuration:

```powershell
$env:OLLAMA_NO_CLOUD = "1"
ollama serve
```

In a second terminal:

```powershell
ollama pull qwen3:4b
ollama show qwen3:4b
$env:LLM_PROVIDER = "ollama"
$env:LLM_MODEL = "qwen3:4b"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:LLM_TIMEOUT_SECONDS = "120"
$env:LLM_MAX_OUTPUT_TOKENS = "2048"
.\.venv\Scripts\python.exe -m app.cli --data-mode synthetic
```

This is an arbitrary-question, multi-turn conversation over public synthetic
fixtures. Type `/quit` to exit or `/reset` to forget context. No transcript is
saved automatically. The recorded examples use the locally installed `qwen3:4b-instruct` tag; its
public download availability is not assumed. The public `qwen3:4b` model is also
tested separately. Thinking is disabled for local tool turns to reduce token
usage; installed-model behavior and hardware still determine latency/quality.

To use the supplied local store resources, place the original six CSVs and
`políticas_da_loja.pdf` in `data/`, then run:

```powershell
.\.venv\Scripts\python.exe -m app.cli --data-mode local
```

Orders are anonymous/denied by default. For an explicitly configured **local demo**
identity, chosen outside conversational input:

```powershell
.\.venv\Scripts\python.exe -m app.cli --data-mode local --enable-demo-identity --demo-customer-id 1
```

Customer 1 is an operator-selected demo binding, not production authentication;
only orders belonging to that identity are accessible. Use another valid ID only
at startup. Chat cannot rebind it. `--data-dir` and `--policy-path` can point to
other authorized local input locations, only in local mode.

Suggested questions (not recorded LLM transcripts):

- `Quais violões disponíveis custam até R$ 1000?`
- `Qual desses é o mais barato? E quanto fica no PIX?`
- `Quero devolver uma compra online que apresentou defeito.`
- `Qual o status do pedido 4? Há rastreamento?`

Actual local order IDs/ownership depend on the loaded files. Claims always refer
to the supplied snapshot, not real-time stock or shipment updates.

## Optional local Streamlit demonstration

A compact, centered black-and-white mini-chat reuses the same Agent, tools, and
local Ollama adapter. Its light/dark toggle persists within the session, and four
Portuguese actions use the same services: catalog/pricing/policy suggestions
submit real agent questions; Meu pedido opens a read-only, authorized synthetic
order view inside the card. Back preserves chat history. It supports arbitrary questions and multi-turn memory, readable catalog
answers, policy section/page captions, loading/error states, and reset. Controls disable during inference. Only the
packaged synthetic fixture is available in this interface; no uploads, private
paths, cloud provider, or customer-identity selector. Customer 1 is fixed by the
existing demo service, and order 2 remains inaccessible. Reset does not rebind it.

Use Python 3.12 (tested) for Streamlit's binary dependencies; the CLI environment
can remain unchanged. From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv-ui
.\.venv-ui\Scripts\python.exe -m pip install -e ".[ui]"
$env:OLLAMA_MODEL = "qwen3:4b"
# Use qwen3:4b-instruct here instead if that local tag is already installed.
.\.venv-ui\Scripts\python.exe -m app.web
```

Start Ollama with cloud disabled and install the model as described above. Open
http://127.0.0.1:8501. The launcher fixes the listen address to loopback, disables
usage telemetry and exception-detail display, and never enables external models.
`OLLAMA_BASE_URL` may select another validated loopback port. UI inference uses a
120-second timeout and 2048 output tokens; Gemini/CLI environment settings do not
change its provider. Stop the server with Ctrl+C. Do not expose it with a tunnel
or public bind; this demo has no authentication system.

Session objects are never globally cached. Each browser session has its own
agent; four exchanges of display/model memory are retained. Refreshing or
closing the tab can lose the session. Policy captions show only retrieved
citation coordinates, never raw tool diagnostics. No conversation export or
transcript persistence is added. Synthetic policy rules are fictitious.

```powershell
.\.venv-ui\Scripts\python.exe -m unittest tests.test_web -v
```

The focused UI tests use Streamlit AppTest, mocked inference, and real synthetic
services; they are not live LLM conversations. When the UI extra is absent,
page tests skip and the session/security tests still run. See
[interface verification](docs/STREAMLIT_DEMO.md) for actual executed results.

## Optional Windows desktop window

The approved Streamlit mini-chat can also open as a native Windows window,
without a browser tab or address bar. In the Python 3.12 UI environment:

```powershell
.\.venv-ui\Scripts\python.exe -m pip install -e ".[desktop]"
$env:OLLAMA_MODEL = "qwen3:4b-instruct"
# Or use the publicly available qwen3:4b tag if already installed.
.\.venv-ui\Scripts\python.exe -m app.desktop
```

Requires Microsoft Edge WebView2 Runtime and Windows .NET support for pywebview.
The approximately 560×720 fixed-size window centers automatically, disables
maximizing/resizing, adapts to smaller screens, retains the existing theme
and session behavior, and starts its own hidden/headless Streamlit worker on an
available 127.0.0.1 port. It waits for readiness before opening the window. Closing
it stops only its owned worker, leaving Ollama and other servers untouched.
`python -m app.web` remains the normal browser option.

No executable packaging, Python API bridge, or new backend is added. Sessions use
private WebView storage; closing loses conversation/theme state. An abrupt OS or
process crash is outside the normal-close cleanup guarantee. Dependencies and
WebView2 must be installed separately; the launcher does not install them.
See [desktop verification](docs/DESKTOP.md) for tests, boundaries, and limitations.

## Gemini synthetic conversation without paid credits

Create/use a Gemini API key belonging to an active **Free Tier project without
linked billing**. Check its model quota in Google AI Studio. Set GEMINI_API_KEY
locally without committing or pasting it into chat, then:

```powershell
$demoGeminiKey = Read-Host "Free-tier Gemini API key" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $demoGeminiKey).Password
$env:LLM_PROVIDER = "gemini"
$env:LLM_MODEL = "gemini-3.1-flash-lite"
$env:GEMINI_FREE_TIER_CONFIRMED = "1"
.\.venv\Scripts\python.exe -m app.cli --data-mode synthetic
```

Free-tier confirmation is an operator attestation, not a programmatic billing
check. The app cannot infer billing state from an inference key. A fixed smoke
scenario is also available; it is not the final interactive interface:

```powershell
.\.venv\Scripts\python.exe -m app.provider_demo --scenario price
```

Approved fixtures live in `app/fixtures/synthetic.json`. They contain fictitious
catalog/orders and synthetic policy text, never copies of the private manual.
Their canonical content hash is pinned; modifying them requires review and an
explicit fingerprint update before cloud use. Gemini refuses local-data mode
before reading store files. Synthetic mode accepts no caller-supplied data path,
policy file, or identity configuration.

Free-form cloud questions are projected locally into a limited approved
Portuguese shop vocabulary, synthetic IDs 1-3, and fixed demo budget values.
The original text and unknown tokens are never forwarded; recognizable contact,
identity, and credential input is blocked. Approved smoke prompts are constants.
Multi-turn history contains only those filtered intents and synthetic results.
This is intentionally limited, **not general-purpose PII anonymization**. Use
Ollama for unrestricted language, budgets, or private customer conversations.
No data is silently routed from Ollama to Gemini.

## Privacy, grounding, and limitations

- Gemini free-tier terms may allow product-improvement use. No actual customer
  records or restricted policy excerpts enter the application cloud path.
- Ollama must be a trusted local server with cloud disabled. Only explicit
  loopback IP/port endpoints are accepted; redirects and proxies are disabled.
- Authorized order outputs omit customer IDs, names, contacts, addresses, payment
  details, and notes. Foreign/nonexistent/malformed orders share one denial body.
  There are no order mutation, refund, cancellation, shipment, or identity tools.
- Tool outputs are minimized: five catalog preview entries (or every match on
  an explicit all-results request), five order lines, four policy excerpts of
  500 characters, and a 12K-character result ceiling. Truncation is marked and
  never presented as complete. Category, availability, budget, sorting, and
  catalog-list wording are enforced in Python. Source references, quality warnings, and unknown fields are retained.
- Retrieved text is untrusted reference data. Prompts direct the model to cite
  sources, preserve cautions, and never execute document instructions. These
  controls do not prove that generated prose is always correct; review actual
  model behavior before claiming success. A first-turn answer without any tool
  evidence is withheld. Later turns may reuse the same session's snapshot evidence.
- PDF parsing targets the supplied numbered-heading profile; no OCR. Missing,
  encrypted, malformed, scanned/blank, or unsupported layouts fail clearly.
- Demo binding is not production authentication or a sandbox against hostile
  Python code. Context is in memory only; old turns may be forgotten.
- HTTP 429/errors stop without retries, automatic provider switching, or a paid
  fallback. Free availability/quotas can change. No model weights are bundled.

## Testing and verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests distinguish synthetic service/CLI tests, mocked native-provider contracts,
actual loopback HTTP against a stub (not a model), original-resource integration
checks, and **opt-in live LLM** smoke tests. Public tests run without private files;
13 offline resource-dependent methods skip when originals are absent. Default tests make
no external model calls. Enable live synthetic checks explicitly:

```powershell
$env:EMPORIO_RUN_LIVE = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_live_providers -v
```

Gemini requires its local key and free-tier confirmation. Ollama requires a
running server and qwen3:4b (or OLLAMA_MODEL for this two-provider smoke suite).
Missing credentials/server produce explicit skips, not invented success. Real local
qwen3:4b-instruct catalog and return regressions have passed. Five actual English
synthetic conversations, with tool traces and answer-origin labels, are in
[examples](examples/README.md). Application guards render critical catalog, quote,
order, and return-timing answers after tool execution; those are distinguished
from model-written prose. The policy follow-up still exposes internal evidence
labels, an acknowledged presentation limitation. Gemini live execution is not
claimed. See [final evaluation](docs/FINAL_EVALUATION.md) for executed results,
public-only installation checks, and audit limits, and
[provider verification](docs/PROVIDERS.md) for dated official links. Prior phase records
remain under `docs/`.

## AI assistance and submission status

Codex assisted with data inspection, architecture, implementation, tests, and
English documentation. Reported tests were actually executed; mocked responses
are not presented as real LLM runs or customer transcripts.

Original CSV/PDF resources, secrets, virtual environments, and build output are
excluded from Git. A GitHub remote exists and already contains earlier commits;
local commits may be ahead of origin/main. Check actual Git state before delivery.

The original three-page Artefact technical challenge has been reviewed locally.
It requires a public GitHub repository link in reply to the recruiting email,
an incremental history, README, and 3–5 interaction examples. The planning history
also records an English PDF via Google Forms instruction. The original recruiting
email is not available for independent verification: confirm that additional
format and the exact deadline with the recruiter. Do not assume one channel
replaces the other, or redistribute original resources without permission.

## What I would improve with more development time

- Broaden multilingual scope and policy evaluations across model versions and
  ambiguous/mixed requests, measuring false refusals, factual errors, and latency.
  Scope decisions are model-based, not a proof against every prompt injection;
  uncertain decisions deliberately prefer clarification over a general answer.
- Replace demo identity binding with verified production authentication and add
  authorized live inventory/order adapters before claiming real-time information.
- Improve local startup diagnostics for unavailable Ollama, missing models, and
  incomplete responses; validate supported Python/WebView2 combinations. The
  current launcher remains a local demonstration, with no paid-provider fallback.

Scope regression tests distinguish mocked classifier/business contracts from
opt-in real Ollama execution. Existing business tests stub the scope decision to
isolate their original assertions; dedicated scope tests exercise the actual
approval gate and fail-closed paths. See [scope verification](docs/SCOPE_FIX.md).
Restart an already-open CLI/Streamlit/desktop process to load updated code.

## Correctness regression checks

Catalog categories, budget, active stock, exhaustive counts, sorting, and list
wording are enforced in Python for explicit requests. Online-return timing is
compared with the window extracted from section 4.1; five days is within the
supplied seven-day window, subject to conditions. Missing/conflicting evidence
yields clarification, not a guessed deadline. These checks do not approve returns.
See [safe publication instructions](docs/PUBLISHING.md) before creating a remote.
See `docs/CORRECTNESS_FIXES.md` for actual tool traces summarized without private
source text, limitations, and opt-in qwen3:4b-instruct regression commands.
