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
