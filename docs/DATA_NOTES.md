# Dataset inspection — provided Artefact resources

The following observations were checked from the seven uploaded challenge files.

| File | Rows | Key fields |
| --- | ---: | --- |
| `products.csv` | 65 | product_id, category_id, price_brl, stock_quantity, status |
| `categories.csv` | 9 | category_id, name |
| `customers.csv` | 50 | customer_id, name, phone, email, city |
| `orders.csv` | 20 | order_id, customer_id, status, tracking_code, total_brl |
| `order_items.csv` | 22 | order_id, product_id, quantity |
| `promotions.csv` | 25 | promotion_id, product_id, discount_percent, is_active |
| `políticas_da_loja.pdf` | 8 pages | store details, payment, return, shipping, discounts, warranty, privacy |

Verified relationships: `products.category_id -> categories.category_id`,
`promotions.product_id -> products.product_id`, `orders.customer_id -> customers.customer_id`,
`order_items.order_id -> orders.order_id`, and `order_items.product_id -> products.product_id`.
No missing referenced IDs were detected in the provided data.

Additional observations:
- Product status: 62 active, 2 discontinued, 1 coming soon.
- Order status: 7 delivered, 1 shipped, 4 confirmed, 4 pending, 4 cancelled.
- Promotions: 4 marked active; 21 not active. Active status alone does not supply a date range.
- Orders have missing tracking codes and estimated delivery values; missing values must not be fabricated.
- The policy PDF (section 6.2) says the 5% PIX discount is not cumulative with promotional pricing.
- The policy PDF contains two different contact numbers: an official phone/WhatsApp number in
  section 1.2, and a separate primary WhatsApp number in section 7. Treat this as a source conflict,
  document the decision, and do not silently conflate them.
- Customers' details should not be exposed to arbitrary requesters. Define a limited demonstration
  identity-check strategy and explicitly document that it is not production authentication.
- In section 7.1 the manual requires consultation of the data source before quoting price/stock.

Suggested first tests: list in-stock violões under R$1000; unavailable product; current promotion
and PIX discount conflict; order status with missing tracking number; return policy for online
purchase; unrelated question; malformed or missing customer identification.
