# Deterministic catalog browser

The previous view held ten records in a 260-pixel scrolling panel. Approximately four were visible at once: the seven-page total was mathematically correct, but hidden rows made it confusing. Product names were static HTML and a separate dropdown controlled details.

The browser now shows four native Streamlit product buttons per page, with a name search, optional category filter, previous/next actions and an explicit displayed range. All 65 records occupy 17 pages before filtering. Filters recalculate the count and reset the page. Search ignores letter case and accents and matches name terms within the current verified catalog result; it does not silently broaden an earlier chat query.

Clicking a row opens details with exact name, category, availability, quantity and the existing Decimal quote. Applicable promotion percentages and base prices come from that same quote, with the non-stacking PIX rule explained. Price conflicts remain unconfirmed. Specific established field disagreements are shown in details. No generated Markdown is parsed into product records. No images, ecommerce actions or additional service were introduced.

Back to catalog retains page, search and category. Durable filter state survives Streamlit's cleanup of widgets that disappear during detail/chat views. Four compact rows limit the need for scrolling; exact pixel scroll offset is not tracked through custom browser scripts. Very long text or smaller displays can still scroll naturally. Chat history remains intact.

Rows use native full-width Streamlit buttons with a right-side chevron. DOM inspection found two internal flex wrappers centering the content even though the button itself was full width. Catalog-scoped styles stretch and left-align those wrappers; no generated Emotion class names are targeted. Each row has identical padding, a muted item number above its medium-weight name, then price and availability. The shared header alone shows LOCAL/DEMO; runtime and identity configuration stays in the README.

The ordered record IDs of the latest verified catalog remain in Agent memory independently of bounded model history. Displayed numbers represent positions in that list, not database IDs; filtering never renumbers them. The ask-about-product action uses that same stable item reference before the shared agent resolves it to its source record. New catalog queries replace references and reset clears them. Order numbers are excluded and authorization is unchanged.

LOCAL and DEMO use their existing startup-bound services and local Ollama. Filtering the product-only DTOs never calls another model or opens another data source. The CLI retains the complete deterministic text list. Catalog generation, promotion calculations, policy retrieval and read-only order ownership checks remain shared Python behavior.

## Verification

The latest full suite executed 197 tests: 196 passed, one Gemini credential/eligibility skip, in 64.766 seconds. This includes five opt-in live Ollama test methods with qwen3:4b-instruct. Mocked providers and Streamlit AppTest are explicitly separate from live inference.

Focused regressions cover all 65 entries across 17 pages, exact row activation, detail/back page restoration, name/category search persistence, filtered page counts, empty results, record references, items 62/63, quote amounts and promotion metadata, missing fields and ordinary conversations. Existing tests cover LOCAL/DEMO isolation, authorization, policy handling and privacy restrictions.

Native Windows checks with real Ollama verified next-page navigation and return to page 2, row activation, combined name/category filtering, promotion details (Kalani: 10%, R$ 323.10, eleven units), item 63 details (R$ 14,922.00, eight units), the ask action and a subsequent stock query returning eight units. The separate DEMO window showed only its two available synthetic products; its promoted nylon instrument cost R$ 90.09 with three units. Light-theme details and the authorized synthetic order view remained functional. General model-written descriptions can still be wordier than the deterministic price/stock answers.

Screenshots and test logs stay outside Git; restricted CSV/PDF source data is not committed.

The alignment correction was verified against the actual Streamlit DOM: each of the three text lines in items 17–20 shared the same left coordinate and each button had the same width and 8px/10px padding, in both themes. Native Windows screenshots confirmed those items in dark and light modes. Clicking empty space inside item 17 opened the correct details; Back restored page 5. The anonymous order view explained startup-bound identity only when opened, with no order details disclosed. The technical footer was absent from chat, catalog and product details; the order view retains only missing delivery-date information, with runtime/access details documented in the README.
