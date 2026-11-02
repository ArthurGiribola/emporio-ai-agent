# One mini-chat, two startup data modes

Previously the launcher passed its environment to Streamlit, but ChatSession
unconditionally created SyntheticTools and the order panel always looked up
synthetic order 1. It did not support original local data.

DEMO remains the default. LOCAL creates the existing Repository, PolicyRetriever,
OrderService and ToolRuntime through `app.data_session.open_tools`, shared with
the CLI. The full PDF is parsed locally; only relevant bounded excerpts enter
the local model context. The same Agent, function calling, session memory,
grounding, scope guard and page are used in both modes. No second application,
dashboard, upload UI, database or cloud integration was added.

## Trusted startup settings

| Environment variable | Behavior |
| --- | --- |
| EMPORIO_DATA_MODE | `demo` (default) or `local`; displayed as DEMO/LOCAL. |
| EMPORIO_DATA_DIR | LOCAL only; defaults to the project's `data` directory independently of working directory. |
| EMPORIO_POLICY_PATH | LOCAL only; defaults to `políticas_da_loja.pdf` in the data directory. |
| EMPORIO_ENABLE_DEMO_IDENTITY | `1` explicitly enables the existing local demo identity adapter; default `0`. |
| EMPORIO_DEMO_CUSTOMER_ID | Required valid customer ID when opting in; never a chat or tool argument. |
| EMPORIO_ORDER_ID | Positive startup-selected order for Meu pedido; default 1. Ownership is still checked on every access. |
| OLLAMA_MODEL | Existing local model setting; verification uses qwen3:4b-instruct. |

The README contains complete PowerShell launch commands. DEMO rejects local file,
identity and order overrides instead of accidentally loading private data. LOCAL
fails on missing/malformed files without falling back to synthetic data. Paths
and IDs have no customer-facing editor. Settings are copied at session creation;
reset and navigation preserve them. Restart to apply trusted configuration changes.

## Privacy and authorization

The interface always constructs a loopback-only Ollama provider regardless of
Gemini/OpenAI environment variables. Agent also rejects an external provider
paired with local tools. Customer records stay inside the repository/service;
the order DTO excludes names, contacts, addresses, notes and customer IDs.
Anonymous, foreign and missing orders share the existing unavailable response.
The configured order number confers no ownership. Demo identity binding is an
operator-controlled local demonstration, not production authentication. It must
not be exposed as a multi-user login mechanism. Chat cannot alter it.

The policy text is reference data, never instructions. UI source labels distinguish
real store policy from synthetic references. Order panels do not label original
records as synthetic. No private sources, policy copies, raw customer data or
local screenshots are committed.

## Full catalog and bounded results

All 65 source products load, including the four unavailable records. The existing
CatalogService already supported `available_only=False`; that validated option is
now available to the shared tool wrapper. Explicit requests to include unavailable
or inactive products opt in, while subsequent ordinary availability questions
restore the default filter. Unavailable rows are clearly marked.

The existing 12,000-character tool-result ceiling is unchanged. Compact JSON
serialization fits all 65 original product rows and metadata under that ceiling.
Larger future results still report truncation; they are never called complete.
Current price/stock/category details use the existing product and pricing tools;
no customer contacts or raw repository objects enter their results.

## Verification results

Windows verification used the existing Python 3.12.15 environment, Streamlit
1.66.1, pywebview 6.2.1 and actual local `qwen3:4b-instruct`. No dependency or
Windows runtime was reinstalled.

The complete automated suite passed: **183 tests in 70.188 seconds, 182 passed,
1 skipped**, no failures/errors. All five opt-in real Ollama methods passed; the
only skip was Gemini's missing credentials/free-tier confirmation. Eleven new
tests cover mode/data isolation, read-only startup binding, missing files, cloud
rejection, complete catalog output, category/stock grounding, original-resource
loading and the same Streamlit page. UI unit tests use mocked inference and real
fixture services; they are separate from the following real native-window checks.

- LOCAL: the Ver produtos action returned 65 actual products in ascending
  effective-price order, marking all four unavailable products. All 29 parsed PDF
  sections were loaded by the session.
- LOCAL: a five-day online return question correctly fell within the source's
  seven-calendar-day window, retained the source's refund conditions and cited
  section 4.1/page 4. This was a timing assessment, not return approval.
- LOCAL: Meu pedido displayed the authorized original record's status, items,
  total and tracking without contacts or notes. Back preserved the conversation.
  A chat claim to be another customer and a foreign order request were denied;
  reopening the panel still showed the original bound order.
- A fresh LOCAL window answered original product category/stock and a subsequent
  promotional PIX-price question using the validated services. The quote did not
  stack the promotional and PIX discounts.
- DEMO: a separately started native window returned its two available synthetic
  products and the synthetic historical order total of 99.00, with explicit
  missing tracking information. Light and dark themes remained functional.
  The fixed window's maximize control remained disabled in both modes.

Raw observations/screenshots stay outside Git. Private CSV/PDF files remain
ignored and untracked. The CLI's existing synthetic/local tests also passed
after switching it to the shared service-construction helper.

## Limits

The original files remain separately supplied and excluded from Git. DEMO works
without them. The read-only data is not a live stock or shipping system. Broad
conversations still have bounded context and inference budgets; reset when needed.
The local model can misclassify ambiguous scope requests or produce variable
wording. Policy excerpts remain bounded and insufficient evidence must be stated.
Changing modes cannot repair missing files or a missing local model. The approved
fixed compact window, themes, chat scrolling and order navigation are unchanged.
