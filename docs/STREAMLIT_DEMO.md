# Local Streamlit demonstration

The single-page interface is an optional adapter around the existing Agent,
Ollama provider, and SyntheticTools. Core services and CLI code are unchanged.
Streamlit 1.66.1 is pinned in the optional `ui` dependency group. No separate API,
frontend application, database, authentication service, or deployment was added.

## Boundaries and decisions

- `python -m app.web` binds only 127.0.0.1:8501, disables usage telemetry and
  exception details, and launches the packaged page. Use this launcher rather
  than changing server bind options. It does not download models automatically.
- Only approved synthetic fixtures are loaded. No private-file uploader/path,
  customer selector, or cloud-provider control exists. Gemini credentials and
  the CLI provider default do not alter the UI's explicit Ollama configuration.
- Each browser session owns a separate Agent and synthetic repository. No global
  cached agent or shared conversation. Existing four-exchange memory is retained;
  display memory is also bounded to four exchanges. Reset clears memory without
  changing demo identity. Refresh can lose the session; no transcripts are saved.
- Order ownership remains in the existing Python service, fixed to demo customer
  1. Order 2 remains unavailable even if conversational input claims customer 2.
  This is a demonstration binding, not production authentication.
- Validated policy section/page coordinates are displayed as synthetic-reference
  captions. Raw diagnostic events, tool arguments, source files, and exceptions
  are never rendered. Tool-driven catalog/pricing/order wording is reused.
- Native responsive Streamlit chat components preserve keyboard input. The
  mini-chat redesign uses scoped static CSS, with no custom JavaScript. User messages render as text; assistant Markdown does
  not allow HTML, and BRL dollar signs are escaped to prevent accidental math.
- Loading and sanitized operational errors are shown in the conversation. No
  refund, return, cancellation, shipment, or identity mutation is added.

## Executed verification — November 1, 2026

Python 3.12.14 with UI installed: **133 tests, 132 passed, 1 skipped**, no
failures/errors, 34.040 seconds. This was the full suite with original local
resources and live Ollama enabled after the currency-rendering correction.
The one skip is Gemini, because no free-tier credentials were configured.

Nine focused tests cover real Streamlit AppTest interactions, multi-turn chat,
reset, citations, sanitized startup/turn errors, loopback enforcement, distinct
sessions, and foreign-order denial. These nine use mocked inference with real
synthetic services; they are not presented as actual LLM execution.

CLI-only Python 3.15.1 without Streamlit: **133 tests, 126 passed, 7 skipped**,
no failures/errors (three optional page tests plus four live tests skipped).
The existing CLI does not require the UI dependency.

Separately, an actual browser session used local qwen3:4b-instruct with synthetic
fixtures: full two-product ascending catalog, PIX quote 90.09, retrieved policy
citations, and uniform denial after a customer-identity change attempt. The local
Ollama server was initially stopped: tests correctly skipped, then the installed
server was started with OLLAMA_NO_CLOUD=1 for genuine execution. No model output
or test success was fabricated. Initial browser inspection caught Markdown math
formatting around currency; the UI-only escaping fix has a regression assertion.

The browser was checked at its narrow default viewport and a 1280x900 desktop
viewport. This is a focused demonstration check, not exhaustive accessibility or
cross-browser certification. Synthetic policy prose remains model-generated and
can overstate missing evidence; citations do not prove every generated sentence.
The fixture's eleven-day reference is intentionally fictitious, not actual store
policy. Critical existing deterministic safeguards remain in place.

## Launch and focused tests

Create a Python environment and install the optional UI dependencies. From the
repository root:

```powershell
$env:OLLAMA_MODEL = "qwen3:4b"
python -m app.web
python -m unittest tests.test_web -v
```

Use an already installed qwen3:4b-instruct tag if preferred. Open
http://127.0.0.1:8501. Stop with Ctrl+C. No remote configuration, push, visibility change, or
submission was performed in this phase. Do not expose the unauthenticated local demonstration
through a public bind or tunnel.


## Reference-based mini-chat refinement

The approved screenshots guide the roughly 620px centered card, pure black
background, thin neutral border, waveform mark, compact header, gray bubbles,
pill suggestions, and bottom composer. The large hero and sidebar are removed.
A native button toggles light/dark CSS tokens stored in session state. No remote
fonts, image backgrounds, UI frameworks, or additional dependencies were added.
Portuguese interface labels match the supplied design; documentation stays English.

The four suggestions submit fixed useful Portuguese questions for available
products, product 1 PIX pricing, authorized demo order 1, and return policies.
They use the existing agent/tools rather than canned answers. A pending-turn
rerun disables controls before inference, then restores them after completion.
Reset clears conversational memory but preserves theme and the fixed identity.

CSS is scoped to named Streamlit containers. A small set of native chat/input/
column selectors styles bubbles and mobile controls against pinned Streamlit
1.66.1; these may require review on a Streamlit upgrade. The conversation has a
330px native scroll area, bounded display history, and an inline native composer.
No model output enters HTML/CSS; answers still use HTML-disabled Markdown with
currency escaping. Privacy and authentication boundaries are unchanged.

Focused AppTest coverage now includes 11 methods, including every suggestion,
theme persistence through chat/reset, and the existing memory/security/error
checks. These use mocked inference and real synthetic services, not live models.
Real local browser checks separately exercised suggestions with qwen3:4b-instruct,
light/dark mode, reset, disabled processing controls, desktop and 390px mobile
sizing. Screenshots were captured from the running application, not generated
mockups. Visual review corrected the light composer surface and mobile column
stacking. The reference is approximated with native Streamlit controls; font and
send-button glyph can differ from the mockup. No backend or CLI change was made.

Final redesign suite: **135 tests, 134 passed, 1 skipped**, no failures/errors,
42.996 seconds, Python 3.12.14 with live Ollama enabled. Gemini skipped because
free-tier credentials are not configured. All 11 focused UI/session tests passed.
