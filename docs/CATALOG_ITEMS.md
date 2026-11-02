# Deterministic catalog presentation

## Diagnosis

The old interface split numbered Markdown into collapsible groups. In the inspected native window, opening the first group displayed its real names and prices: the reported literal empty `1.` could not be reproduced there. However, the final group's title incorrectly included the price disclaimer. All 65 validated tool rows were present. This established a brittle text-parsing presentation path, rather than missing CSV rows or a confirmed CSS defect.

List positions also differed from source product IDs. Without an explicit map, asking for item 63 could incorrectly query source ID 63. The ordered source IDs of the latest verified list now remain in Agent memory independently of bounded LLM history. New lists replace that map and reset clears it. Category filtering and pagination preserve its original numbers. Order references are excluded; ambiguous positions request clarification. Explicit `produto ID 81` still means a source-ID lookup for technical testing.

## Implementation

The model selects validated tools. A product-only immutable CatalogView then reads names, categories, exact quantities, availability and Decimal prices from the existing services. No generated Markdown is parsed into products. Large verified catalog calls finish without asking the model to retype every row. Scope checks, policy evidence, authorization and execution budgets remain active. CLI answers retain the complete deterministic text list.

Streamlit and pywebview use the same internal view: ten products per page, previous/next controls, category filtering and product selection for details. The back arrow preserves chat history. Empty matches remain conversational; partial results explicitly state their count. Ordinary non-catalog answers stay as chat messages. No new server, dependency or dashboard was added.

Prices use the existing quote service without stacking PIX on promotions. Conflicting promotions produce an unconfirmed price instead of a guessed value. Product warnings name established disagreements (for example, name versus description brand) rather than repeating generic caveats.

## Verification

Full suite: **195 tests, 194 passed, one Gemini credential skip**, 64.900 seconds, including five opt-in real Ollama test methods with `qwen3:4b-instruct`. Mocked AppTest/provider regressions are distinct from those live executions. Regressions cover 65 rows across seven pages, stable category-filtered positions, items 62/63, reset/history pruning, promotions, missing information, escaped content, empty results and ordinary conversations. AppTest restores the main module to avoid contaminating Windows multiprocessing tests.

Native Windows validation with original data and local Ollama traversed pages 1 through 7 and back, selected item 63 (Yamaha Kit 3, eight units), and filtered to percussion while keeping positions 48, 62 and 63. Back navigation preserved the conversation and the stock follow-up for item 63 returned eight units. Screenshots and local test logs are kept outside the repository; original data and restricted policy files are not added to Git.

The subsequent native chat query for item 62 returned seven units and its precise Pearl/Tama brand disagreement. Both light and dark themes remained functional. A five-day online return question after these catalog turns stayed in the chat and correctly explained the seven-day window with section/page references.

The inspected first group did not reproduce the exact reported empty-number symptom. The entire text-splitting path has nevertheless been removed. References always concern the latest verified list; use a product name when uncertain. Existing local-model, runtime and bounded-context limitations still apply.
