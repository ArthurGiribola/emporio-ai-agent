# Focused desktop corrections

## Catalog diagnosis

The desktop's ChatSession constructs SyntheticTools directly, without private
paths or configurable identities. The fixture is valid: three catalog records,
two active/in-stock. Independent service and unfiltered tool calls return product
1 and product 3. This is not an empty-data or desktop-mode issue.

A real qwen3:4b-instruct replay with an earlier ukulele/budget turn returned both
reported broad questions correctly; the original failing session/tool log is
unavailable, so its precise model arguments are not asserted. Controlled calls
through the actual pre-fix runtime demonstrate two deterministic failure paths:

- First exact question with query=sintéticos, category_id=9, max_price_brl=1000
  retained all three qualifiers and returned zero, despite two available records.
- Second exact question with query=lista, category_id=9, max_price_brl=1000 cleared
  category/budget but retained literal lista and returned zero.

The old broad-scope expression required adjacent todos os produtos; it missed
Liste todos ... in the first question. Generic Portuguese words also survived
literal query matching. These confirmed argument-normalization gaps explain how
valid fixtures can produce the reported symptom; the missing original trace
prevents attribution of a particular bad argument to that historical LLM run.

Explicit exhaustive requests now establish fresh budget/category scope, retaining
only filters stated in the current question. Generic words in the exact reports
are removed. Generic exhaustive lists use effective prices including active
promotions, with no stacked PIX discount; explicit effective-price sorting is
also supported for category requests. Existing list-price budget semantics remain
unchanged and are disclosed. Pricing conflicts fail, rather than inventing prices.

Empty datasets, no matches, and tool errors have separate structured states;
empty datasets receive their own answer and tool failures never become an empty
catalog claim. Complete/partial counts remain explicit. Mocked regressions cover
the exact two-turn questions with stale/malformed model filters, effective sort
order, explicit filter preservation, empty data, and failures. A real post-fix
Ollama replay returned both products for both questions.


## Authorized order detail view

Meu pedido now navigates within Streamlit session state to a compact read-only
view; it does not ask the model to invent a layout or open another window. It
calls the existing session-bound OrderService for fixed synthetic order 1.
Ownership is verified before the safe DTO is returned. Anonymous and foreign
identities receive the same safe unavailability explanation. No identity input,
customer contacts, notes, mutation, or private-source mode was added.

Back preserves chat messages and model memory. The view shows recorded status,
quantities/names, historical total, known tracking or an explicit missing-value
message, and a status-based monochrome progress indicator. Cancelled/unknown
statuses do not invent transport milestones. Missing lines and service failures
have separate explanations. Progress is a visual projection of recorded status,
not evidence of intermediate events. Tests cover authorized display/back,
anonymous/foreign denial, cancellation, missing items/tracking, and safe errors.
25 focused UI/order tests passed before this milestone commit.


## Fixed utility window

The launcher now uses pywebview's public screen dimensions and supported window
options: resizable=False, fullscreen=False, maximized=False. On Windows the
pinned WinForms backend disables MaximizeBox for a non-resizable window. Native
moving, minimizing, focusing and close behavior remain unchanged. No OS hooks,
custom title bar, or separate application was introduced. Size is capped at
560×720 with margins for smaller screen resolutions; very small screens may
require vertical page scrolling, while the message/order regions remain scrollable.
Nine focused launcher tests passed, including smaller-screen sizing and window
flags. The real native accessibility tree showed Maximizar disabled.

Final full suite with live local Ollama enabled: **150 tests, 149 passed, 1 skipped**,
no failures/errors, 42.348 seconds. Gemini skipped because its free-tier key is
not configured. AppTest/native-window mocks are distinct from actual Ollama and
native window checks. Original privacy, return, catalog, and ownership tests
remain passing. No push, visibility change, submission, or history rewrite.

Actual native checks returned both reported catalog questions with two results,
confirmed back navigation retained the first conversation, and showed the safe
order DTO in the same fixed-size window. Dark/light order screenshots were
captured. Scoped contrast rules keep order text and catalog list items legible
in both themes. Earlier open application processes need a restart to load edits.
